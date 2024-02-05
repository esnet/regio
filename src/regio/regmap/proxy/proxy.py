#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import dispatcher, router, variable
from ..spec import address, array, field, meta, register, structure, union

#---------------------------------------------------------------------------------------------------
# Keep the proxy namespace as clean as possible to allow acting as an attribute passthrough. The
# more crowded the namespace, the higher the chance of failing to route an attribute due to Python
# finding it on the proxy class itself rather than on the node being proxied. The context serves as
# a general purpose object for carrying meta-data through a chain of proxy routing operations. This
# allows passing state and configuration from the first node in a chain to the last.
class Proxy:
    def __init__(self, node, ctx, *pargs, **kargs):
        # Don't use super() here because the mixins can (and generally will) override __setattr__.
        object.__setattr__(self, '___node___', node)
        object.__setattr__(self, '___context___', ctx)
        object.__setattr__(self, '__doc__', type(node.spec).__doc__)
        super().__init__(*pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class ProxyInfo:
    def __init__(self, single_cls, group_cls, variable_cls, node_types):
        self.single_cls = single_cls
        self.group_cls = group_cls
        self.variable_cls = variable_cls
        self.node_types = node_types

#---------------------------------------------------------------------------------------------------
class Context:
    def __init__(self, proxy_info, pargs, kargs):
        super().__init__()

        self.proxy_info = proxy_info
        self.pargs = tuple(pargs)
        self.kargs = dict(kargs)

    def copy(self, *pargs, **kargs):
        return type(self)(*pargs, self.proxy_info, tuple(self.pargs), dict(self.kargs), **kargs)

    def new_proxy(self, node, chain, *pargs, **kargs):
        ntype = type(node)
        for info in self.proxy_info:
            if ntype not in info.node_types:
                continue

            if chain is not None and chain.is_group:
                return info.group_cls(node, self, chain, *pargs, **kargs)
            return info.single_cls(node, self, chain, *pargs, **kargs)

        raise TypeError(f'Unable to match {node!r} to a proxy.')

#---------------------------------------------------------------------------------------------------
class IOContext(Context):
    def __init__(self, io, *pargs, **kargs):
        super().__init__(*pargs, **kargs)
        self.io = io

    def copy(self, io=None, *pargs, **kargs):
        return super().copy(*pargs, self.io if io is None else io, **kargs)

    def new_variable(self, node, chain, *pargs, **kargs):
        ntype = type(node)
        for info in self.proxy_info:
            if ntype in info.node_types:
                return info.variable_cls(node, self, chain, *pargs, **kargs)

        raise TypeError(f'Unable to match {node!r} to a variable.')

#---------------------------------------------------------------------------------------------------
# Helper for instantiating a proxy for IO operations on a node.
def for_io(spec, io, proxy_info, *pargs, **kargs):
    # Set up the context to be shared by all proxies rooted at the given specification.
    ctx = IOContext(io, proxy_info, pargs, kargs)

    # Create the proxy.
    return ctx.new_proxy(meta.data_get(spec), None)

#---------------------------------------------------------------------------------------------------
class ForStructureIOByPathName(Proxy, dispatcher.ForStructureIO, router.ByPathName): ...
class ForArrayIOByPathIndex(Proxy, dispatcher.ForArrayIO, router.ByPathIndex): ...
class ForRegisterIOByPathName(Proxy, dispatcher.ForRegisterIO, router.ByPathName): ...
class ForFieldIOByPathName(Proxy, dispatcher.ForFieldIO, router.ByPathName): ...

class ForStructureIOByPathNameGroup(
        Proxy, dispatcher.ForStructureIOGroup, router.ByPathNameGroup): ...
class ForArrayIOByPathIndexGroup(Proxy, dispatcher.ForArrayIOGroup, router.ByPathIndexGroup): ...
class ForRegisterIOByPathNameGroup(
        Proxy, dispatcher.ForRegisterIOGroup, router.ByPathNameGroup): ...
class ForFieldIOByPathNameGroup(Proxy, dispatcher.ForFieldIOGroup, router.ByPathNameGroup): ...

FOR_IO_BY_PATH_PROXY_INFO = (
    ProxyInfo(
        ForStructureIOByPathName,
        ForStructureIOByPathNameGroup,
        variable.StructureVariable,
        (address.Node, array.ElementNode, structure.Node, union.Node),
    ),
    ProxyInfo(
        ForArrayIOByPathIndex,
        ForArrayIOByPathIndexGroup,
        variable.ArrayVariable,
        (array.Node,),
    ),
    ProxyInfo(
        ForRegisterIOByPathName,
        ForRegisterIOByPathNameGroup,
        variable.RegisterVariable,
        (register.Node,),
    ),
    ProxyInfo(
        ForFieldIOByPathName,
        ForFieldIOByPathNameGroup,
        variable.FieldVariable,
        (field.Node,),
    ),
)

def for_io_by_path(spec, io, *pargs, **kargs):
    return for_io(spec, io, FOR_IO_BY_PATH_PROXY_INFO, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
def start_io(proxy):
    proxy.___context___.io.start()

def stop_io(proxy):
    proxy.___context___.io.stop()
