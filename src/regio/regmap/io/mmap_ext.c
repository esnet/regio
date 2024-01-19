#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

#include <endian.h>
#include <stdbool.h>
#include <stdint.h>

/* Defined to simplify read/write/update macros below. */
#define htobe8(_x) ((uint8_t)(_x))
#define htole8(_x) ((uint8_t)(_x))
#define be8toh(_x) ((uint8_t)(_x))
#define le8toh(_x) ((uint8_t)(_x))

/*
 * Notes for implementing multi-word support:
 * - The int_from_bytes_impl function implements the int.from_bytes method.
 *   - https://github.com/python/cpython/blob/main/Objects/longobject.c#L6102
 * - The _PyLong_FromByteArray function does the conversion from an array of bytes to a Python int
 *   (PyLong type).
 *   - https://github.com/python/cpython/blob/main/Objects/longobject.c#L814
 * - The int_to_bytes_impl function implements the int.to_bytes method.
 *   - https://github.com/python/cpython/blob/main/Objects/longobject.c#L6040
 * - The _PyLong_AsByteArray function does the conversion from a Python int to an array of bytes.
 *   - https://github.com/python/cpython/blob/main/Objects/longobject.c#L929
 * - Look into using the buffer protocol in conjunction with array.array() for passing multi-word
 *   blocks between Python and C.
 */

/*------------------------------------------------------------------------------------------------*/
typedef struct {
    PyObject_HEAD

    uintptr_t base_addr;
    unsigned int word_width;
    unsigned int bulk_width;
    unsigned int bulk_size;
    bool little_endian;
}  MmapDirectIO;

/*------------------------------------------------------------------------------------------------*/
static PyObject* MmapDirectIO_new(
    PyTypeObject* type, PyObject* Py_UNUSED(pargs), PyObject* Py_UNUSED(kargs)) {
    return type->tp_alloc(type, 0);
}

/*------------------------------------------------------------------------------------------------*/
static void MmapDirectIO_dealloc(PyObject* _self) {
    Py_TYPE(_self)->tp_free(_self);
}

/*------------------------------------------------------------------------------------------------*/
static bool MmapDirectIO_is_valid_data_width(unsigned int width) {
    switch (width) {
    case 8:
    case 16:
    case 32:
    case 64:
        return true;
    }
    return false;
}

/*------------------------------------------------------------------------------------------------*/
static int MmapDirectIO_init(PyObject* _self, PyObject* pargs, PyObject* kargs) {
    static char *kargs_list[] = {
        "base_addr",
        "word_width",
        "bulk_width",
        "little_endian",
        NULL
    };

    MmapDirectIO* self = (typeof(self))_self;
    int little_endian = 0;

    int rv = PyArg_ParseTupleAndKeywords(
        pargs, kargs, "KIIp", kargs_list,
        &self->base_addr, &self->word_width,
        &self->bulk_width, &little_endian);
    if (rv == 0)
        return -1;

    if (!MmapDirectIO_is_valid_data_width(self->word_width)) {
        PyErr_Format(PyExc_ValueError, "Invalid word data width %u", self->word_width);
        return -1;
    }

    if (!MmapDirectIO_is_valid_data_width(self->bulk_width)) {
        PyErr_Format(PyExc_ValueError, "Invalid bulk data width %u", self->bulk_width);
        return -1;
    }

    self->bulk_size = self->bulk_width / self->word_width;
    self->little_endian = little_endian != 0;

    return 0;
}

/*------------------------------------------------------------------------------------------------*/
static PyObject* MmapDirectIO_repr(PyObject *_self) {
    MmapDirectIO* self = (typeof(self))_self;

    return PyUnicode_FromFormat(
        "%s(%p, %u, %u, %R)", Py_TYPE(self)->tp_name, self->base_addr,
        self->word_width, self->bulk_width, self->little_endian ? Py_True : Py_False);
}

/*------------------------------------------------------------------------------------------------*/
#define __ptr_read(_width, _self, _offset, _value) { \
    uint##_width##_t __tmp = ((volatile typeof(__tmp)*)((_self)->base_addr))[(_offset)]; \
    __tmp = (_self)->little_endian ? le##_width##toh(__tmp) : be##_width##toh(__tmp); \
    (_value) = (typeof(_value))__tmp; \
}

#define _ptr_read(_width, _self, _offset, _value) \
    __ptr_read(_width, _self, _offset, _value)

static PyObject* MmapDirectIO_read(PyObject* _self, PyObject* args) {
    MmapDirectIO* self = (typeof(self))_self;
    unsigned long long offset;
    unsigned long long size;
    unsigned long long value;

    if (!PyArg_ParseTuple(args, "KK", &offset, &size))
        return NULL;

    /* Handle fast path accesses. */
    if (size == 1) {
        switch (self->word_width) {
        case 8: _ptr_read(8, self, offset, value); break;
        case 16: _ptr_read(16, self, offset, value); break;
        case 32: _ptr_read(32, self, offset, value); break;
        case 64: _ptr_read(64, self, offset, value); break;
        default: value = 0; break; /* word_width is validated during init and is read-only. */
        }
        return PyLong_FromLongLong(value);
    }

    if (size == self->bulk_size) {
        offset /= self->bulk_size;
        switch (self->bulk_width) {
        case 8: _ptr_read(8, self, offset, value); break;
        case 16: _ptr_read(16, self, offset, value); break;
        case 32: _ptr_read(32, self, offset, value); break;
        case 64: _ptr_read(64, self, offset, value); break;
        default: value = 0; break; /* bulk_width is validated during init and is read-only. */
        }
        return PyLong_FromLongLong(value);
    }

    /* TODO: Fill in slow path for multi-word accesses. See notes at top of file. */

    PyErr_Format(PyExc_ValueError, "Invalid read size of %u from offset 0x%08x", size, offset);
    return NULL;
}

/*------------------------------------------------------------------------------------------------*/
#define __ptr_write(_width, _self, _offset, _value) { \
    uint##_width##_t __tmp = (typeof(__tmp))(_value); \
    __tmp = (_self)->little_endian ? htole##_width(__tmp) : htobe##_width(__tmp); \
    ((volatile typeof(__tmp)*)((_self)->base_addr))[(_offset)] = __tmp; \
}

#define _ptr_write(_width, _self, _offset, _value) \
    __ptr_write(_width, _self, _offset, _value)

static PyObject* MmapDirectIO_write(PyObject* _self, PyObject* args) {
    MmapDirectIO* self = (typeof(self))_self;
    unsigned long long offset;
    unsigned long long size;
    unsigned long long value; //PyObject* value;

    //if (!PyArg_ParseTuple(args, "KKO", &offset, &size, &value))
    if (!PyArg_ParseTuple(args, "KKK", &offset, &size, &value))
        return NULL;

    /* Handle fast path accesses. */
    if (size == 1) {
        switch (self->word_width) {
        case 8: _ptr_write(8, self, offset, value); break;
        case 16: _ptr_write(16, self, offset, value); break;
        case 32: _ptr_write(32, self, offset, value); break;
        case 64: _ptr_write(64, self, offset, value); break;
        default: break; /* word_width is validated during init and is read-only. */
        }
        Py_RETURN_NONE;
    }

    if (size == self->bulk_size) {
        offset /= self->bulk_size;
        switch (self->bulk_width) {
        case 8: _ptr_write(8, self, offset, value); break;
        case 16: _ptr_write(16, self, offset, value); break;
        case 32: _ptr_write(32, self, offset, value); break;
        case 64: _ptr_write(64, self, offset, value); break;
        default: break; /* bulk_width is validated during init and is read-only. */
        }
        Py_RETURN_NONE;
    }

    /* TODO: Fill in slow path for multi-word accesses. See notes at top of file. */

    PyErr_Format(PyExc_ValueError, "Invalid write size of %u to offset 0x%08x", size, offset);
    Py_RETURN_NONE;
}

/*------------------------------------------------------------------------------------------------*/
#define __ptr_update(_width, _self, _offset, _clr_mask, _set_mask) {\
    uint##_width##_t __tmp = ((volatile typeof(__tmp)*)((_self)->base_addr))[(_offset)]; \
    __tmp = (_self)->little_endian ? le##_width##toh(__tmp) : be##_width##toh(__tmp); \
    __tmp &= (typeof(__tmp))(_clr_mask); \
    __tmp |= (typeof(__tmp))(_set_mask); \
    __tmp = (_self)->little_endian ? htole##_width(__tmp) : htobe##_width(__tmp); \
    ((volatile typeof(__tmp)*)((_self)->base_addr))[(_offset)] = __tmp; \
}

#define _ptr_update(_width, _self, _offset, _clr_mask, _set_mask) \
    __ptr_update(_width, _self, _offset, _clr_mask, _set_mask)

static PyObject* MmapDirectIO_update(PyObject* _self, PyObject* args) {
    MmapDirectIO* self = (typeof(self))_self;
    unsigned long long offset;
    unsigned long long size;
    unsigned long long clr_mask; //PyObject* clr_mask;
    unsigned long long set_mask; //PyObject* set_mask;

    //if (!PyArg_ParseTuple(args, "KKOO", &offset, &size, &clr_mask, &set_mask))
    if (!PyArg_ParseTuple(args, "KKKK", &offset, &size, &clr_mask, &set_mask))
        return NULL;

    /* Handle fast path accesses. */
    if (size == 1) {
        switch (self->word_width) {
        case 8: _ptr_update(8, self, offset, clr_mask, set_mask); break;
        case 16: _ptr_update(16, self, offset, clr_mask, set_mask); break;
        case 32: _ptr_update(32, self, offset, clr_mask, set_mask); break;
        case 64: _ptr_update(64, self, offset, clr_mask, set_mask); break;
        default: break; /* word_width is validated during init and is read-only. */
        }
        Py_RETURN_NONE;
    }

    if (size == self->bulk_size) {
        offset /= self->bulk_size;
        switch (self->bulk_width) {
        case 8: _ptr_update(8, self, offset, clr_mask, set_mask); break;
        case 16: _ptr_update(16, self, offset, clr_mask, set_mask); break;
        case 32: _ptr_update(32, self, offset, clr_mask, set_mask); break;
        case 64: _ptr_update(64, self, offset, clr_mask, set_mask); break;
        default: break; /* bulk_width is validated during init and is read-only. */
        }
        Py_RETURN_NONE;
    }

    /* TODO: Fill in slow path for multi-word accesses. See notes at top of file. */

    PyErr_Format(PyExc_ValueError, "Invalid update size of %u at offset 0x%08x", size, offset);
    Py_RETURN_NONE;
}

/*------------------------------------------------------------------------------------------------*/
static PyMethodDef MmapDirectIO_methods[] = {
    {
        .ml_name = "read",
        .ml_meth = MmapDirectIO_read,
        .ml_flags = METH_VARARGS,
        .ml_doc = "Read size words starting from the given offset.",
    },
    {
        .ml_name = "write",
        .ml_meth = MmapDirectIO_write,
        .ml_flags = METH_VARARGS,
        .ml_doc = "Write size words starting at the given offset.",
    },
    {
        .ml_name = "update",
        .ml_meth = MmapDirectIO_update,
        .ml_flags = METH_VARARGS,
        .ml_doc = "Update size words starting at the given offset.",
    },
    {}
};

/*------------------------------------------------------------------------------------------------*/
static PyMemberDef MmapDirectIO_members[] = {
    {
        .name = "base_addr",
        .type = T_ULONGLONG,
        .offset = offsetof(MmapDirectIO, base_addr),
        .flags = READONLY,
        .doc = "Base address of the memory mapped region."
    },
    {
        .name = "word_width",
        .type = T_INT,
        .offset = offsetof(MmapDirectIO, word_width),
        .flags = READONLY,
        .doc = "Width of a data word (in bits)."
    },
    {
        .name = "bulk_width",
        .type = T_INT,
        .offset = offsetof(MmapDirectIO, bulk_width),
        .flags = READONLY,
        .doc = "Width of a data word (in bits) for bulk accesses."
    },
    {
        .name = "little_endian",
        .type = T_BOOL,
        .offset = offsetof(MmapDirectIO, little_endian),
        .flags = READONLY,
        .doc = "Endianess of the memory mapped region."
    },
    {}
};

/*------------------------------------------------------------------------------------------------*/
static PyTypeObject MmapDirectIOType = {
    .ob_base = PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "mmap_ext.MmapDirectIO",
    .tp_doc = PyDoc_STR("MmapDirectIO object"),
    .tp_basicsize = sizeof(MmapDirectIO),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = MmapDirectIO_new,
    .tp_dealloc = MmapDirectIO_dealloc,
    .tp_init = MmapDirectIO_init,
    .tp_repr = MmapDirectIO_repr,
    .tp_methods = MmapDirectIO_methods,
    .tp_members = MmapDirectIO_members,
};

/*------------------------------------------------------------------------------------------------*/
static PyModuleDef mmap_ext_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "mmap_ext",
    .m_doc = "C extension module for performing low-level IO on a memory mapped region.",
    .m_size = -1,
};

/*------------------------------------------------------------------------------------------------*/
PyMODINIT_FUNC PyInit_mmap_ext(void) {
    if (PyType_Ready(&MmapDirectIOType) < 0)
        return NULL;

    PyObject* mod = PyModule_Create(&mmap_ext_module);
    if (mod == NULL)
        return NULL;

    Py_INCREF(&MmapDirectIOType);
    if (PyModule_AddObject(mod, "MmapDirectIO", (PyObject*)&MmapDirectIOType) < 0) {
        Py_DECREF(&MmapDirectIOType);
        Py_DECREF(mod);
        return NULL;
    }
    return mod;
}
