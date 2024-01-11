#---------------------------------------------------------------------------------------------------
__all__ = ()

import os
import pathlib
import struct

from . import io
from ..spec import info

#---------------------------------------------------------------------------------------------------
class StreamIO(io.IO):
    # https://docs.python.org/3/library/struct.html#format-strings
    STRUCT_FORMATS = {
        'endian': {
            io.Endian.LITTLE: '<',
            io.Endian.BIG: '>',
        },
        'width': {
            8: 'B',
            16: 'H',
            32: 'L',
            64: 'Q',
        },
    }

    def __init__(self, data_width, endian=io.Endian.NATIVE, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        if data_width % 8 != 0:
            raise ValueError(f'Data width {data_width} must be a multiple of 8 bits.')
        self.octets = data_width // 8

        # Construct a struct object for packing/unpacking values to/from a byte stream.
        self._struct = struct.Struct(
            self.STRUCT_FORMATS['endian'][endian.get()] +
            self.STRUCT_FORMATS['width'][data_width])

    def stream_open(self):
        raise NotImplementedError

    def stream_seek(self, offset):
        self._stream.seek(offset * self.octets)

    def start(self):
        if not self.started:
            self._stream = self.stream_open()
            super().start()

    def stop(self):
        if self.started:
            self._stream.close()
            del self._stream
            super().stop()

    def read(self, offset):
        self.stream_seek(offset)
        return self._struct.unpack(self._stream.read(self.octets))[0]

    def write(self, offset, value):
        self.stream_seek(offset)
        self._stream.write(self._struct.pack(value))

#---------------------------------------------------------------------------------------------------
class FileStreamIO(StreamIO):
    def __init__(self, path, file_size, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)

        self.path = path
        self.file_size = file_size

    def stream_open(self):
        # Pre-size the file to ensure that enough memory is allocated for all offsets.
        with self.path.open('ab') as fo:
            os.ftruncate(fo.fileno(), self.file_size)

        # Create an unbuffered binary file object for raw IO.
        # https://docs.python.org/3/library/io.html
        return self.path.open('r+b', 0)

#---------------------------------------------------------------------------------------------------
class FileStreamIOForSpec(FileStreamIO):
    def __init__(self, spec, path, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(path, region.octets, region.data_width, *pargs, **kargs)
