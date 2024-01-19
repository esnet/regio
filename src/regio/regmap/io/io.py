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

    def read(self, offset, size):
        raise NotImplementedError

    def write(self, offset, size, value):
        raise NotImplementedError

    def update(self, offset, size, clr_mask, set_mask):
        value = self.read(offset, size)
        value &= clr_mask
        value |= set_mask
        self.write(offset, size, value)

    def read_region(self, region):
        return (self.read(region.offset.absolute, region.size) >> region.shift) & region.mask

    def write_region(self, region, value):
        self.write(region.offset.absolute, region.size, (value & region.mask) << region.shift)

    def update_region(self, region, value):
        mask = region.mask << region.shift
        self.update(region.offset.absolute, region.size, ~mask, (value << region.shift) & mask)

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

    def read(self, offset, size):
        value = self.buffer.get(offset)
        if value is not None:
            return value[1]

        if self.default is None:
            return self.load(offset, size)
        return self.default

    def write(self, offset, size, value):
        self.buffer[offset] = (size, value)

    def load(self, offset, size):
        value = self.llio.read(offset, size)
        self.buffer[offset] = (size, value)
        return value

    def store(self, offset, size, value):
        self.buffer[offset] = (size, value)
        self.llio.write(offset, size, value)

    def load_region(self, region):
        return self.load(region.offset.absolute, region.size)

    def store_region(self, region, value):
        self.store(region.offset.absolute, region.size, value)

    def sync(self):
        for offset, value in self.buffer.sorted():
            self.store(offset, value[0], value[1])

    def drop(self):
        self.buffer.clear()

    def flush(self):
        self.sync()
        self.drop()

#---------------------------------------------------------------------------------------------------
class ZeroIO(IO):
    def read(self, offset, size): return 0
    def write(self, offset, size, value): ...
    def update(self, offset, size, clr_mask, set_mask): ...

#---------------------------------------------------------------------------------------------------
class ListIO(IO):
    def __init__(self, size, data_width, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.size = size
        self.data_width = data_width
        self.data_mask = (1 << data_width) - 1

    def start(self):
        if not self.started:
            self._words = [0] * self.size
            super().start()

    def stop(self):
        if self.started:
            del self._words
            super().stop()

    def read(self, offset, size):
        value = 0
        offset += size
        while size > 0:
            offset -= 1
            size -= 1
            value <<= self.data_width
            value |= self._words[offset] & self.data_mask
        return value

    def write(self, offset, size, value):
        while size > 0:
            self._words[offset] = value & self.data_mask
            value >>= self.data_width
            offset += 1
            size -= 1

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

    def read(self, offset, size):
        return self._words.get(offset, 0)

    def write(self, offset, size, value):
        self._words[offset] = value
