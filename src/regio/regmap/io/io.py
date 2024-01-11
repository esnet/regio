#---------------------------------------------------------------------------------------------------
__all__ = ()

import enum
import sys

from ..spec import info

#---------------------------------------------------------------------------------------------------
class Endian(enum.Enum):
    NATIVE = enum.auto()
    LITTLE = enum.auto()
    BIG = enum.auto()

    def get(self):
        if self is Endian.NATIVE:
            return Endian[sys.byteorder.upper()]
        return self

#---------------------------------------------------------------------------------------------------
class IO:
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)
        self.started = False

    def __enter__(self):
        self.start()

        # Allow caller to bind the object in a 'with X() as x' statement.
        return self

    def __exit__(self, *pargs):
        self.stop()

        # Don't suppress exceptions. Pass along to the caller.
        return False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    # TODO: pass size for multi-word read
    def read(self, offset):
        raise NotImplementedError

    # TODO: pass size for multi-word write
    def write(self, offset, value):
        raise NotImplementedError

    # TODO: pass size for multi-word update
    def update(self, offset, clr_mask, set_mask):
        value = self.read(offset)
        value &= clr_mask
        value |= set_mask
        self.write(offset, value)

    def read_region(self, region):
        return (self.read(region.offset.absolute) >> region.shift) & region.mask

    def write_region(self, region, value):
        self.write(region.offset.absolute, (value & region.mask) << region.shift)

    def update_region(self, region, value):
        mask = region.mask << region.shift
        self.update(region.offset.absolute, ~mask, (value << region.shift) & mask)

#---------------------------------------------------------------------------------------------------
class IOBuffer(dict):
    def sorted(self):
        for offset, value in sorted(self.items(), key=lambda pair: pair[0]):
            yield (offset, value)

#---------------------------------------------------------------------------------------------------
class BufferedIO(IO):
    def __init__(self, llio, buffer=None, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.llio = llio
        self.buffer = IOBuffer() if buffer is None else buffer
        self.default = None

    def start(self):
        self.llio.start()

    def stop(self):
        self.llio.stop()

    def read(self, offset):
        value = self.buffer.get(offset, self.default)
        if value is None:
            value = self.load(offset)
        return value

    def write(self, offset, value):
        self.buffer[offset] = value

    def load(self, offset):
        value = self.llio.read(offset)
        self.buffer[offset] = value
        return value

    def store(self, offset, value):
        self.buffer[offset] = value
        self.llio.write(offset, value)

    def load_region(self, region):
        return self.load(region.offset.absolute)

    def store_region(self, region, value):
        self.store(region.offset.absolute, value)

    def sync(self):
        for offset, value in self.buffer.sorted():
            self.store(offset, value)

    def drop(self):
        self.buffer.clear()

    def flush(self):
        self.sync()
        self.drop()

#---------------------------------------------------------------------------------------------------
class ZeroIO(IO):
    def read(self, offset):
        return 0

    def write(self, offset, value): ...
    def update(self, offset, clr_mask, set_mask): ...

#---------------------------------------------------------------------------------------------------
class ListIO(IO):
    def __init__(self, size, *pargs, **kargs):
        super().__init__(*pargs, **kargs)
        self.size = size

    def start(self):
        if not self.started:
            self._words = [0] * self.size
            super().start()

    def stop(self):
        if self.started:
            del self._words
            super().stop()

    def read(self, offset):
        return self._words[offset]

    def write(self, offset, value):
        self._words[offset] = value

#---------------------------------------------------------------------------------------------------
class ListIOForSpec(ListIO):
    def __init__(self, spec, *pargs, **kargs):
        super().__init__(info.size_of(spec), *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class DictIO(IO):
    def start(self):
        if not self.started:
            self._words = {}
            super().start()

    def stop(self):
        if self.started:
            del self._words
            super().stop()

    def read(self, offset):
        return self._words.get(offset, 0)

    def write(self, offset, value):
        self._words[offset] = value
