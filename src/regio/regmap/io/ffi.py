#---------------------------------------------------------------------------------------------------
__all__ = ()

import ctypes as _ctypes
import os

#---------------------------------------------------------------------------------------------------
class CType:
    class pointer:
        NULL = None

        # This is defined due to how ctypes handles return values from function calls. If not sub-
        # classed, ctypes attempts automatic conversions to native Python types for pointers. By
        # sub-classing a pointer type, the conversion is prevented and the address from the result
        # is available via the "value" attribute. Refer to the last two paragraphs for the class
        # ctypes._SimpleCData found at:
        # https://docs.python.org/3/library/ctypes.html#ctypes-fundamental-data-types-2
        class void(_ctypes.c_void_p): ...

    # Note: Use "value" as the field name for consistency with the descriptor that ctypes provides.
    class integer:
        class u8:
            class le(_ctypes.c_uint8): ...
            be = le # For consistency when using string-based lookups.

        class u16:
            class le(_ctypes.LittleEndianStructure): _fields_ = (('value', _ctypes.c_uint16),)
            class be(_ctypes.BigEndianStructure): _fields_ = (('value', _ctypes.c_uint16),)

        class u32:
            class le(_ctypes.LittleEndianStructure): _fields_ = (('value', _ctypes.c_uint32),)
            class be(_ctypes.BigEndianStructure): _fields_ = (('value', _ctypes.c_uint32),)

        class u64:
            class le(_ctypes.LittleEndianStructure): _fields_ = (('value', _ctypes.c_uint64),)
            class be(_ctypes.BigEndianStructure): _fields_ = (('value', _ctypes.c_uint64),)

    @staticmethod
    def cast_to_pointer(addr, ctype):
        return _ctypes.cast(addr, _ctypes.POINTER(ctype))

    @staticmethod
    def cast_to_array_pointer(addr, ctype, count):
        return _ctypes.cast(addr, _ctypes.POINTER(ctype * count))

    def read(self, ctype, addr):
        return self.cast_to_pointer(addr, ctype).contents.value

    def write(self, ctype, addr, value):
        self.cast_to_pointer(addr, ctype).contents.value = value

    def update(self, ctype, addr, clr_mask, set_mask):
        ptr = self.cast_to_pointer(addr, ctype).contents
        value = ptr.value
        value &= clr_mask
        value |= set_mask
        ptr.value = value

#---------------------------------------------------------------------------------------------------
class LibC:
    def __init__(self):
        import ctypes.util as _cutil

        # Get the C library's path.
        # https://docs.python.org/3/library/ctypes.html#finding-shared-libraries
        self.path = _cutil.find_library('c')
        if self.path is None:
            raise AssertionError('Missing libc?')

        # Load the library.
        # https://docs.python.org/3/library/ctypes.html#loading-shared-libraries
        self.handle = _ctypes.CDLL(self.path, use_errno=True)

        # Export selected foreign functions.
        # https://docs.python.org/3/library/ctypes.html#foreign-functions
        self._export_mmap()
        self._export_munmap()

    def os_error(self):
        errno = _ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

    def _export_mmap(self):
        # From man 2 mmap:
        # - void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset)
        # - Return value:
        #   - On success: void* to mapped area.
        #   - On errors:  (void*)-1 and sets errno.
        self.MMAP_FAILED = CType.pointer.void(-1).value
        self._mmap = self.handle.mmap
        self._mmap.restype = CType.pointer.void
        self._mmap.argtypes = (
            CType.pointer.void, # addr
            _ctypes.c_size_t, # length
            _ctypes.c_int, # prot
            _ctypes.c_int, # flags
            _ctypes.c_int, # fd
            _ctypes.c_long, # offset
        )

    def mmap(self, addr, length, prot, flags, fd, offset):
        rv = self._mmap(addr, length, prot, flags, fd, offset)
        if rv.value == self.MMAP_FAILED:
            self.os_error()
        return rv

    def _export_munmap(self):
        # From man 2 mmap:
        # - int munmap(void *addr, size_t length)
        # - Return value:
        #   - On success: 0
        #   - On errors: -1 and sets errno.
        self.MUNMAP_FAILED = -1
        self._munmap = self.handle.munmap
        self._munmap.restype = _ctypes.c_int # Automatically converted to Python int on return.
        self._munmap.argtypes = (
            CType.pointer.void, # addr
            _ctypes.c_size_t, # length
        )

    def munmap(self, addr, length):
        rv = self._munmap(addr, length)
        if rv == self.MUNMAP_FAILED:
            self.os_error()

#---------------------------------------------------------------------------------------------------
# Instantiate on import of the module.
ctype = CType()
