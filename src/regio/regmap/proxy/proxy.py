#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import dispatcher, router, variable
from ..io import io
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

    def select(self, node, chain):
        return self

    def _new_proxy(self, node, chain, *pargs, **kargs):
        ntype = type(node)
        for info in self.proxy_info:
            if ntype not in info.node_types:
                continue

            if chain is not None and chain.is_group:
                return info.group_cls(node, self, chain, *pargs, **kargs)
            return info.single_cls(node, self, chain, *pargs, **kargs)

        raise TypeError(f'Unable to match {node!r} to a proxy.')

    def new_proxy(self, node, chain, *pargs, **kargs):
        ctx = self.select(node, chain)
        return ctx._new_proxy(node, chain, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class IOContext(Context):
    def __init__(self, io, *pargs, **kargs):
        super().__init__(*pargs, **kargs)
        self.io = io

    def copy(self, io=None, *pargs, **kargs):
        return super().copy(*pargs, self.io if io is None else io, **kargs)

    def select(self, node, chain):
        # This method determines whether the current context can be used to access the given node or
        # whether a new context using a different IO accessor is needed (and creates it if so). The
        # idea is to provide a hook to detect the change between IO domains (via a node that defines
        # a protocol), swap out the current IO accessor with a new one that redirects through the
        # protocol and then carry on as if nothing happened. All of the child nodes that fall within
        # the indirect view will inherit the new redirected IO transparently.

        # IO access can only be performed on singular nodes.
        if chain is not None and chain.is_group:
            return self

        # The node does not introduce a protocol (i.e. not a new indirect view), so re-use the
        # current context's IO. If the node is contained within an indirect view, the current IO
        # will already be bound to the appropriate protocol.
        proto = node.protocol
        if proto is None:
            return self

        # The node introduces a protocol, so all subsequent child nodes are accessed through an
        # indirect memory view.

        # Check if the current context is setup for indirect access via the required protocol (this
        # occurs when creating a new proxy or variable for a node).
        llio = self.io.llio if isinstance(self.io, io.BufferedIO) else self.io
        if isinstance(llio, io.ProtocolIO) and llio.protocol is proto:
            return self

        # Create a proxy for the node's parent to give the protocol instance access to the registers
        # needed to perform the IO accesses through the indirect memory view. Make sure the new
        # proxy is created on the low-level IO to handle cases when the context is buffered.
        if node.parent is None:
            raise AssertionError('Attempting IO via protocol on root node.')
        proxy = self.copy(llio)._new_proxy(node.parent, None)

        # Allow test hooks to override the protocol for faking the underlying accesses.
        override = self.kargs.get('protocol_override')
        if override is not None:
            proto = override(node.spec)

        # Create a new IO accessor that redirects through the protocol.
        proto_io = io.ProtocolIO(proto, llio, proxy)
        if self.io.started:
            proto_io.start()

        # Create a new IO context for proxy objects contained within the indirect memory view.
        return self.copy(proto_io)

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
class ForNumericIOByPathName(Proxy, dispatcher.ForNumericIO, router.ByPathName): ...

class ForStructureIOByPathNameGroup(
        Proxy, dispatcher.ForStructureIOGroup, router.ByPathNameGroup): ...
class ForArrayIOByPathIndexGroup(Proxy, dispatcher.ForArrayIOGroup, router.ByPathIndexGroup): ...
class ForNumericIOByPathNameGroup(Proxy, dispatcher.ForNumericIOGroup, router.ByPathNameGroup): ...

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
        ForNumericIOByPathName,
        ForNumericIOByPathNameGroup,
        variable.RegisterVariable,
        (register.Node,),
    ),
    ProxyInfo(
        ForNumericIOByPathName,
        ForNumericIOByPathNameGroup,
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
