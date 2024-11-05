#---------------------------------------------------------------------------------------------------
__all__ = (
    'DevMmapIO',
    'DevMmapIOForSpec',
    'DevMmapProtocol',
    'DevMmapProtocolForSpec',
    'DictIO',
    'DictProtocol',
    'FileMmapIO',
    'FileMmapIOForSpec',
    'FileMmapProtocol',
    'FileMmapProtocolForSpec',
    'FileStreamIO',
    'FileStreamIOForSpec',
    'FileStreamProtocol',
    'FileStreamProtocolForSpec',
    'ListIO',
    'ListIOForSpec',
    'ListProtocol',
    'ListProtocolForSpec',
    'Protocol',
    'Transaction',
    'WrappedIOProtocol',
    'WrappedIOProtocolForSpec',
    'ZeroIO',
    'ZeroProtocol',
)

from .io import (
    DictIO, DictProtocol,
    ListIO, ListProtocol,
    Protocol,
    Transaction,
    WrappedIOProtocol,
    ZeroIO, ZeroProtocol,
)
from .mmap import (
    DevMmapIO, DevMmapProtocol,
    FileMmapIO, FileMmapProtocol,
)
from .stream import (
    FileStreamIO, FileStreamProtocol,
)

from ..spec import info

#---------------------------------------------------------------------------------------------------
class WrappedIOProtocolForSpec(WrappedIOProtocol):
    def __init__(self, spec, *pargs, **kargs):
        super().__init__(spec, None, spec, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class DevMmapIOForSpec(DevMmapIO):
    def __init__(self, spec, path, *pargs, **kargs):
        super().__init__(path, info.data_width_of(spec), *pargs, **kargs)

class DevMmapProtocolForSpec(WrappedIOProtocolForSpec):
    WRAPPED_IO = DevMmapIOForSpec

#---------------------------------------------------------------------------------------------------
class FileMmapIOForSpec(FileMmapIO):
    def __init__(self, spec, path, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(path, region.octets, region.data_width, *pargs, **kargs)

class FileMmapProtocolForSpec(WrappedIOProtocolForSpec):
    WRAPPED_IO = FileMmapIOForSpec

#---------------------------------------------------------------------------------------------------
class FileStreamIOForSpec(FileStreamIO):
    def __init__(self, spec, path, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(path, region.octets, region.data_width, *pargs, **kargs)

class FileStreamProtocolForSpec(WrappedIOProtocolForSpec):
    WRAPPED_IO = FileStreamIOForSpec

#---------------------------------------------------------------------------------------------------
class ListIOForSpec(ListIO):
    def __init__(self, spec, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(region.size, region.data_width, *pargs, **kargs)

class ListProtocolForSpec(WrappedIOProtocolForSpec):
    WRAPPED_IO = ListIOForSpec
