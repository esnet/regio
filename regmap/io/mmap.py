#---------------------------------------------------------------------------------------------------
__all__ = ()

import mmap
import os
import pathlib

from . import ffi
from . import io
from ..spec import info

#---------------------------------------------------------------------------------------------------
class MmapIO(io.IO):
    WORD_CTYPES = {
        8: {
            io.Endian.LITTLE: ffi.ctype.integer.u8.le,
            io.Endian.BIG: ffi.ctype.integer.u8.be,
        },
        16: {
            io.Endian.LITTLE: ffi.ctype.integer.u16.le,
            io.Endian.BIG: ffi.ctype.integer.u16.be,
        },
        32: {
            io.Endian.LITTLE: ffi.ctype.integer.u32.le,
            io.Endian.BIG: ffi.ctype.integer.u32.be,
        },
        64: {
            io.Endian.LITTLE: ffi.ctype.integer.u64.le,
            io.Endian.BIG: ffi.ctype.integer.u64.be,
        },
    }

    def __init__(self, path, data_width,
                 mmap_size=None, offset=0, endian=io.Endian.NATIVE,
                 *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        if data_width % 8 != 0:
            raise ValueError(f'Data width {data_width} must be a multiple of 8 bits.')
        self.octets = data_width // 8

        if offset % self.octets != 0:
            raise ValueError(
                f'Offset 0x{offset:x} must be aligned to word size of {self.octets} bytes.')

        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        self.path = path

        if mmap_size is None:
            mmap_size = path.stat().st_size

        self.page_no = (offset + mmap.PAGESIZE - 1) // mmap.PAGESIZE
        self.page_offset = offset % mmap.PAGESIZE
        self.mmap_size = mmap_size - self.page_no * mmap.PAGESIZE

        # Get the C type for a data word.
        self._word_ctype = self.WORD_CTYPES[data_width][endian.get()]

    def start(self):
        if self.started:
            return

        # Map the file's memory region into the virtual address space.
        with self.path.open('r+b') as fo:
            self._addr_p = ffi.libc.mmap(
                ffi.ctype.pointer.NULL, self.mmap_size, mmap.PROT_READ | mmap.PROT_WRITE,
                mmap.MAP_SHARED, fo.fileno(), self.page_no * mmap.PAGESIZE)

        # Set the base of the memory region's first word.
        self._base_addr = self._addr_p.value + self.page_offset
        super().start()

    def stop(self):
        if not self.started:
            return

        # Unmap the memory region from the virtual address space.
        ffi.libc.munmap(self._addr_p, self.mmap_size)
        del self._addr_p
        del self._base_addr
        super().stop()

#---------------------------------------------------------------------------------------------------
class MmapIndirectIO(MmapIO):
    def read(self, offset):
        return ffi.ctype.read(self._word_ctype, self._base_addr + offset * self.octets)

    def write(self, offset, value):
        ffi.ctype.write(self._word_ctype, self._base_addr + offset * self.octets, value)

    def update(self, offset, clr_mask, set_mask):
        ffi.ctype.update(
            self._word_ctype, self._base_addr + offset * self.octets, clr_mask, set_mask)

#---------------------------------------------------------------------------------------------------
class MmapDirectIO(MmapIO):
    def start(self):
        if not self.started:
            # Setup the mapping.
            super().start()

            # Create a ctypes pointer to an array of words for the entire mapping.
            self._ptr = ffi.ctype.cast_to_pointer(self._base_addr, self._word_ctype)

    def stop(self):
        if self.started:
            del self._ptr
            super().stop()

    def read(self, offset):
        return self._ptr[offset].value

    def write(self, offset, value):
        self._ptr[offset].value = value

    def update(self, offset, clr_mask, set_mask):
        ptr = self._ptr[offset]
        value = ptr.value
        value &= clr_mask
        value |= set_mask
        ptr.value = value

#---------------------------------------------------------------------------------------------------
class DevMmapIO(MmapDirectIO): ...
class DevMmapIOForSpec(DevMmapIO):
    def __init__(self, spec, path, *pargs, **kargs):
        super().__init__(path, info.data_width_of(spec), *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class FileMmapIO(MmapDirectIO):
    def __init__(self, path, file_size, *pargs, **kargs):
        super().__init__(path, *pargs, mmap_size=file_size, **kargs)
        self.file_size = file_size

    def start(self):
        if self.started:
            return

        # Pre-size the file to ensure that enough memory is allocated for all offsets.
        with self.path.open('ab') as fo:
            os.ftruncate(fo.fileno(), self.file_size)

        # Map the file into the virtual address space.
        super().start()

#---------------------------------------------------------------------------------------------------
class FileMmapIOForSpec(FileMmapIO):
    def __init__(self, spec, path, *pargs, **kargs):
        region = info.region_of(spec)
        super().__init__(path, region.octets, region.data_width, *pargs, **kargs)
