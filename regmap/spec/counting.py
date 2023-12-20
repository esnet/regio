#---------------------------------------------------------------------------------------------------
__all__ = ()

import math

from . import meta
from ..types import counter

#---------------------------------------------------------------------------------------------------
# TODO: make a dataclass?
class RegionInfo:
    def __init__(self):
        self.offset = None
        self.data_width = None
        self.size = 0
        self.oid = ()
        self.ordinal = None
        self.register = None

#---------------------------------------------------------------------------------------------------
class Region:
    def __init__(self, domain, parent, node):
        self.domain = domain
        self.parent = parent
        self.node = node
        self.info = RegionInfo()

        if parent is None:
            self.outer_data_width = domain.data_width
            self.active = domain.words
            self.info.oid = (len(domain.regions),)
        else:
            self.outer_data_width = parent.data_width
            self.active = parent.active
            self.info.oid = parent.info.oid + (len(parent.regions),)
        self.data_width = self.outer_data_width

        self.info.ordinal = domain.ordinal
        domain.ordinal += 1

        self.regions = []
        node.init_region(self)
        self.regions = tuple(self.regions)
        node.region = self.info

    @property
    def size(self):
        return self.active.size

    def add(self, node):
        self.regions.append(self.domain.new_region(self, node))

    def inc(self, size):
        self.active.inc(size)

    def goto(self, offset):
        if self.info.offset is not None:
            raise AssertionError(
                f'Attempting to set offset for {self.node.spec!r} after beginning inner region.')

        pos = self.active.current.relative
        if offset < pos:
            raise AssertionError(f'Attempting to move offset of {self.node.spec!r} backwards.')
        self.inc(offset - pos)

    def align(self, size):
        self.active.align(size)

    def pause(self, reset=False):
        return self.active.pause(reset)

    def restore(self):
        return self.active.restore()

    def restore_inc(self):
        return self.active.restore_inc()

    def _align_to_outer(self, data_width=None):
        w_outer = self.outer_data_width
        w_inner = self.data_width if data_width is None else data_width
        if w_outer != w_inner:
            # Outer and inner regions align at k*(n_inner*w_inner) = k*(n_outer*w_outer) with k>=0.
            w_gcd = math.gcd(w_outer, w_inner)
            n_outer, n_inner = w_inner // w_gcd, w_outer // w_gcd

            # Align using inner scale when transitioning from inner to outer (count in w_inner).
            # Align using outer scale when transitioning from outer to inner (count in w_outer).
            if data_width is None:
                n = n_inner
            else:
                # Change the data width for all counting in the inner region.
                self.data_width = w_inner
                n = n_outer
            self.align(n)

    def begin(self, reset=False, data_width=None):
        if self.info.offset is not None:
            raise AssertionError(f'Attempting to restart inner region for {self.node.spec!r}.')

        if not reset:
            self._align_to_outer(data_width)
        self.info.offset = self.pause(reset)

        if self.in_bits:
            self.info.base = self.parent.info.base

    def end(self, inc=True):
        if self.info.offset is None:
            raise AssertionError(
                f'Attempting to end inner region for {self.node.spec!r} without having begun.')

        self.info.data_width = self.data_width
        self.info.size = self.restore_inc() if inc else self.restore()
        if inc:
            self._align_to_outer()

        width = self.data_width * self.info.size
        if self.in_bits:
            pos = self.info.offset
            width = self.info.size
            offset, shift = divmod(pos.absolute, self.data_width)
            size = (shift + width + self.data_width - 1) // self.data_width

            self.info.offset = self.info.base.copy()
            self.info.offset.inc(offset)

            self.info.pos = pos
            self.info.width = width
            self.info.mask = (1 << width) - 1
            self.info.size = size
            self.info.shift = shift
        elif self.info.register is not None:
            self.info.width = width
            self.info.shift = 0
            self.info.mask = (1 << width) - 1

        self.info.nibbles = (width + 4 - 1) // 4
        self.info.octets = (width + 8 - 1) // 8

    @property
    def in_words(self):
        return self.active is self.domain.words

    @property
    def in_bits(self):
        return self.active is self.domain.bits

    def begin_bits(self):
        bits = self.domain.bits
        if self.active is bits:
            raise AssertionError(f'Attempting to restart inner bit region for {self.node.spec!r}.')

        bits.pause(True)
        self.active = bits
        self.info.base = self.info.offset

    def end_bits(self):
        bits = self.domain.bits
        words = self.domain.words
        if self.active is not bits:
            raise AssertionError(
                f'Attempting to end inner bit region for {self.node.spec!r} without having begun.')

        width = self.restore()
        if width > 0:
            words.inc((width + self.data_width - 1) // self.data_width) # Align to word boundary.
        self.active = words

        self.info.register = self.domain.register
        self.domain.register += 1

#---------------------------------------------------------------------------------------------------
class Domain:
    def __init__(self, data_width, *specs, force=False, **kargs):
        super().__init__(**kargs)

        self.data_width = data_width
        self.words = counter.Counter()
        self.bits = counter.Counter()

        self.ordinal = 0
        self.register = 0

        # Note: This loop should not be condensed into a comprehension due to the length being used
        # for accounting purposes by the regions during iteration.
        self.regions = []
        for spec in specs:
            node = meta.data_get(spec)
            if not force and node.region is not None:
                raise AssertionError(f'Regmap spec {spec!r} has already been counted.')
            self.regions.append(self.new_region(None, node))
        self.regions = tuple(self.regions)

    def new_region(self, parent, node):
        return Region(self, parent, node)
