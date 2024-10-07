#---------------------------------------------------------------------------------------------------
__all__ = (
    'DevMmapIO',
    'DevMmapIOForSpec',
    'DictIO',
    'FileMmapIO',
    'FileMmapIOForSpec',
    'FileStreamIO',
    'FileStreamIOForSpec',
    'ListIO',
    'ListIOForSpec',
    'ZeroIO',
)

from .io import DictIO, ListIO, ZeroIO
from .mmap import DevMmapIO, FileMmapIO
from .stream import FileStreamIO

from ..spec import info

#---------------------------------------------------------------------------------------------------
class DevMmapIOForSpec(DevMmapIO):
    def __init__(self, spec, path, *pargs, **kargs):
        super().__init__(path, info.data_width_of(spec), *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class FileMmapIOForSpec(FileMmapIO):
    def __init__(self, spec, path, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(path, region.octets, region.data_width, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class FileStreamIOForSpec(FileStreamIO):
    def __init__(self, spec, path, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(path, region.octets, region.data_width, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class ListIOForSpec(ListIO):
    def __init__(self, spec, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(region.size, region.data_width, *pargs, **kargs)
