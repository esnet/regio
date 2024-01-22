#---------------------------------------------------------------------------------------------------
__all__ = ()

import mmap
import os
import pathlib
import struct

from . import ffi
from . import io
from ..spec import info

try:
    from . import mmap_ext
except ImportError:
    mmap_ext = None

#---------------------------------------------------------------------------------------------------
class MmapIO(io.IO):
    WORD_CTYPES = {
        1: {
            io.Endian.LITTLE: ffi.ctype.integer.u8.le,
            io.Endian.BIG: ffi.ctype.integer.u8.be,
        },
        2: {
            io.Endian.LITTLE: ffi.ctype.integer.u16.le,
            io.Endian.BIG: ffi.ctype.integer.u16.be,
        },
        4: {
            io.Endian.LITTLE: ffi.ctype.integer.u32.le,
            io.Endian.BIG: ffi.ctype.integer.u32.be,
        },
        8: {
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

        octets = data_width // 8
        if octets not in self.WORD_CTYPES:
            raise ValueError(f'Missing C type for data width of {data_width} bits.')

        if offset % octets != 0:
            raise ValueError(
                f'Offset 0x{offset:x} must be aligned to word size of {octets} bytes.')
        self.octets = octets

        # Setup the information needed for mapping the memory region.
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        self.path = path

        if mmap_size is None:
            mmap_size = path.stat().st_size

        self.page_no = (offset + mmap.PAGESIZE - 1) // mmap.PAGESIZE
        self.page_offset = offset % mmap.PAGESIZE
        self.mmap_size = mmap_size - self.page_no * mmap.PAGESIZE
        self.libc = ffi.LibC()

        # Get the C type for accessing a single data word.
        self.endian = endian.get()
        self._word_ctype = self.WORD_CTYPES[octets][self.endian]

        # Get the largest valid C type for accessing words in bulk.
        psize = struct.calcsize('P') # Size in bytes of C pointer.
        if psize > octets and psize in self.WORD_CTYPES:
            self._bulk_ctype = self.WORD_CTYPES[psize][self.endian]
        else:
            self._bulk_ctype = self._word_ctype

        self.word_width = data_width
        self.word_mask = (1 << data_width) - 1
        self.bulk_width = psize * 8
        self.bulk_mask = (1 << self.bulk_width) - 1
        self.bulk_size = self.bulk_width // data_width

    def start(self):
        if self.started:
            return

        # Map the file's memory region into the virtual address space.
        with self.path.open('r+b') as fo:
            self._addr_p = self.libc.mmap(
                ffi.ctype.pointer.NULL, self.mmap_size, mmap.PROT_READ | mmap.PROT_WRITE,
                mmap.MAP_SHARED, fo.fileno(), self.page_no * mmap.PAGESIZE)

        # Set the base of the memory region's first word.
        self._base_addr = self._addr_p.value + self.page_offset
        super().start()

    def stop(self):
        if not self.started:
            return

        # Unmap the memory region from the virtual address space.
        self.libc.munmap(self._addr_p, self.mmap_size)
        del self._addr_p
        del self._base_addr
        super().stop()

#---------------------------------------------------------------------------------------------------
class MmapIndirectIO(MmapIO):
    def start(self):
        if not self.started:
            # Setup the mapping.
            super().start()

            # Create a ctypes pointer to an array of words for the entire mapping.
            self._word_ptr = ffi.ctype.cast_to_pointer(self._base_addr, self._word_ctype)
            self._bulk_ptr = ffi.ctype.cast_to_pointer(self._base_addr, self._bulk_ctype)

    def stop(self):
        if self.started:
            del self._word_ptr
            del self._bulk_ptr
            super().stop()

    def _operations(self, offset, size):
        # Single word access.
        if size < self.bulk_size:
            return [(self._word_ptr, offset, size, self.word_width, self.word_mask)]

        # Multi word access. Split the access to minimize operations while respecting alignment.
        ops = []
        count = offset % self.bulk_size
        if count != 0:
            ops.append((self._word_ptr, offset, count, self.word_width, self.word_mask))
            offset += count
            size -= count

        if size >= self.bulk_size:
            bulk_offset = offset // self.bulk_size
            bulk_count = size // self.bulk_size
            ops.append((self._bulk_ptr, bulk_offset, bulk_count, self.bulk_width, self.bulk_mask))

            count = bulk_count * self.bulk_size
            offset += count
            size -= count

        if size > 0:
            ops.append((self._word_ptr, offset, size, self.word_width, self.word_mask))
        return ops

    def read(self, offset, size):
        value = 0
        shift = 0
        for ptr, offset, count, width, mask in self._operations(offset, size):
            while count > 0:
                value |= (ptr[offset].value & mask) << shift
                shift += width
                count -= 1
        return value

    def write(self, offset, size, value):
        for ptr, offset, count, width, mask in self._operations(offset, size):
            while count > 0:
                ptr[offset].value = value & mask
                value >>= width
                count -= 1

    def update(self, offset, size, clr_mask, set_mask):
        for ptr, offset, count, width, mask in self._operations(offset, size):
            while count > 0:
                p = ptr[offset]
                value = p.value
                value &= clr_mask & mask
                value |= set_mask & mask
                p.value = value

                clr_mask >>= width
                set_mask >>= width
                count -= 1

#---------------------------------------------------------------------------------------------------
# Use the C extension module if present. If not, fall back to using indirect IO via ctypes.
if mmap_ext is None:
    import logging
    logging.warning(
        f'{__name__}: Falling back to indirect mmap IO. Build C extension for direct IO support.')

    MmapDirectIO = MmapIndirectIO
else:
    class MmapDirectIO(MmapIO):
        def start(self):
            if not self.started:
                # Setup the mapping.
                super().start()

                # Instantiate a direct IO object from the C extension.
                self._direct_io = mmap_ext.MmapDirectIO(
                    self._base_addr, self.word_width, self.bulk_width,
                    self.endian == io.Endian.LITTLE)

        def stop(self):
            if self.started:
                del self._direct_io
                super().stop()

        def read(self, offset, size):
            return self._direct_io.read(offset, size)

        def write(self, offset, size, value):
            self._direct_io.write(offset, size, value)

        def update(self, offset, size, clr_mask, set_mask):
            self._direct_io.update(offset, size, clr_mask, set_mask)

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
