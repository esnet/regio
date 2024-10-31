#---------------------------------------------------------------------------------------------------
__all__ = ()

import enum
import sys

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
class Transaction:
    def __init__(self, region, value=None):
        self.region = region
        self.value = value

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

    def transact(self, txn):
        region = txn.region
        value = txn.value

        if value is None:
            value = self.read(region.offset.absolute, region.size)
            txn.value = (value >> region.shift) & region.mask
        elif region.pos is not None:
            mask = region.mask << region.shift
            value = (value << region.shift) & mask
            self.update(region.offset.absolute, region.size, ~mask, value)
        else:
            value = (value & region.mask) << region.shift
            self.write(region.offset.absolute, region.size, value)

#---------------------------------------------------------------------------------------------------
class Protocol:
    def __init__(self, spec, if_name):
        self.spec = spec # Captured to provide regmap information to implementations.
        self.if_name = if_name
        self.started = False

    def start(self, proxy):
        self.started = True

    def stop(self, proxy):
        self.started = False

    def read(self, proxy, offset, size):
        raise NotImplementedError

    def write(self, proxy, offset, size, value):
        raise NotImplementedError

    def update(self, proxy, offset, size, clr_mask, set_mask):
        value = self.read(proxy, offset, size)
        value &= clr_mask
        value |= set_mask
        self.write(proxy, offset, size, value)

    def transact(self, proxy, txn):
        region = txn.region
        value = txn.value

        if value is None:
            value = self.read(proxy, region.offset.absolute, region.size)
            txn.value = (value >> region.shift) & region.mask
        elif region.pos is not None:
            mask = region.mask << region.shift
            value = (value << region.shift) & mask
            self.update(proxy, region.offset.absolute, region.size, ~mask, value)
        else:
            value = (value & region.mask) << region.shift
            self.write(proxy, region.offset.absolute, region.size, value)

#---------------------------------------------------------------------------------------------------
class ProtocolIO(IO):
    def __init__(self, proto, llio, proxy, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.protocol = proto
        self.llio = llio

        if proto.if_name is not None:
            proxy = getattr(proxy, proto.if_name)
        self.proxy = proxy

    def start(self):
        if not self.started:
            self.llio.start()
            self.protocol.start(self.proxy)
            super().start()

    def stop(self):
        if self.started:
            self.protocol.stop(self.proxy)
            self.llio.stop()
            super().stop()

    def read(self, offset, size):
        return self.protocol.read(self.proxy, offset, size)

    def write(self, offset, size, value):
        self.protocol.write(self.proxy, offset, size, value)

    def update(self, offset, size, clr_mask, set_mask):
        self.protocol.update(self.proxy, offset, size, clr_mask, set_mask)

    def transact(self, txn):
        self.protocol.transact(self.proxy, txn)

#---------------------------------------------------------------------------------------------------
class WrappedIOProtocol(Protocol):
    WRAPPED_IO = None

    def __init__(self, spec, if_name, *pargs, **kargs):
        super().__init__(spec, if_name)
        self._wrapped_io = self.WRAPPED_IO(*pargs, **kargs)

    def start(self, proxy):
        if not self.started:
            self._wrapped_io.start()
            super().start(proxy)

    def stop(self, proxy):
        if self.started:
            super().stop(proxy)
            self._wrapped_io.stop()

    def read(self, proxy, offset, size):
        return self._wrapped_io.read(offset, size)

    def write(self, proxy, offset, size, value):
        self._wrapped_io.write(offset, size, value)

    def update(self, proxy, offset, size, clr_mask, set_mask):
        self._wrapped_io.update(offset, size, clr_mask, set_mask)

    def transact(self, proxy, txn):
        self._wrapped_io.transact(txn)

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

class ZeroProtocol(WrappedIOProtocol):
    WRAPPED_IO = ZeroIO

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

class ListProtocol(WrappedIOProtocol):
    WRAPPED_IO = ListIO

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

class DictProtocol(WrappedIOProtocol):
    WRAPPED_IO = DictIO
