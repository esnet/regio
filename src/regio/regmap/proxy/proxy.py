#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import dispatcher, router, variable
from ..spec import address, array, field, meta, register, structure, union

#---------------------------------------------------------------------------------------------------
# Keep the proxy namespace as clean as possible to allow acting as an attribute passthrough. The
# more crowded the namespace, the higher the chance of failing to route an attribute due to Python
# finding it on the proxy class itself rather than on the node being proxied. The context serves as
# a general purpose object use by the proxies.
class Proxy:
    def __init__(self, node, ctx, *pargs, **kargs):
        # Don't use super() here because the mixins can override __setattr__.
        object.__setattr__(self, '___node___', node)
        object.__setattr__(self, '___context___', ctx)
        object.__setattr__(self, '__doc__', type(node.spec).__doc__)
        super().__init__(*pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class Context:
    def __init__(self, types, pargs, kargs):
        super().__init__()

        self.types = types
        self.pargs = pargs
        self.kargs = kargs

    def copy(self, *pargs, **kargs):
        return type(self)(*pargs, self.types, tuple(self.pargs), dict(self.kargs), **kargs)

    def new_proxy(self, node, *pargs, **kargs):
        ntype = type(node)
        for proxy_cls, _, node_types in self.types:
            if ntype in node_types:
                return proxy_cls(node, self, *pargs, **kargs)

        raise TypeError(f'Unable to match {node!r} to a proxy.')

#---------------------------------------------------------------------------------------------------
class IOContext(Context):
    def __init__(self, io, *pargs, **kargs):
        super().__init__(*pargs, **kargs)
        self.io = io

    def copy(self, io=None, *pargs, **kargs):
        return super().copy(*pargs, self.io if io is None else io, **kargs)

    def new_variable(self, node, *pargs, **kargs):
        ntype = type(node)
        for _, var_cls, node_types in self.types:
            if ntype in node_types:
                return var_cls(node, self, *pargs, **kargs)

        raise TypeError(f'Unable to match {node!r} to a variable.')

#---------------------------------------------------------------------------------------------------
# Helper for instantiating a proxy for IO operations on a node.
def for_io(spec, io, types, *pargs, **kargs):
    # Set up the context to be shared by all proxies rooted at the given specification.
    ctx = IOContext(io, types, pargs, kargs)

    # Create the proxy.
    return ctx.new_proxy(meta.data_get(spec))

#---------------------------------------------------------------------------------------------------
class ForStructureIOByPathName(Proxy, dispatcher.ForStructureIO, router.ByPathName): ...
class ForArrayIOByPathIndex(Proxy, dispatcher.ForArrayIO, router.ByPathIndex): ...
class ForRegisterIOByPathName(Proxy, dispatcher.ForRegisterIO, router.ByPathName): ...
class ForFieldIOByPathName(Proxy, dispatcher.ForFieldIO, router.ByPathName): ...

FOR_IO_BY_PATH_TYPES = (
    # Each entry has the form: (proxy_cls, variable_cls, node_types)
    (
        ForStructureIOByPathName,
        variable.StructureVariable,
        (address.Node, array.ElementNode, structure.Node, union.Node),
    ),
    (
        ForArrayIOByPathIndex,
        variable.ArrayVariable,
        (array.Node,),
    ),
    (
        ForRegisterIOByPathName,
        variable.RegisterVariable,
        (register.Node,),
    ),
    (
        ForFieldIOByPathName,
        variable.FieldVariable,
        (field.Node,),
    ),
)

def for_io_by_path(spec, io, *pargs, **kargs):
    return for_io(spec, io, FOR_IO_BY_PATH_TYPES, *pargs, **kargs)

def start_io(proxy):
    proxy.___context___.io.start()

def stop_io(proxy):
    proxy.___context___.io.stop()
