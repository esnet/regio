#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc
import functools

from ..spec import meta

#---------------------------------------------------------------------------------------------------
# Keep the proxy namespace as clean as possible to allow acting as an attribute passthrough. The
# more crowded the namespace, the higher the chance of failing to route an attribute due to Python
# finding it on the proxy class itself rather than on the node being proxied. The context serves as
# a general purpose object for carrying meta-data through a chain of proxy routing operations. This
# allows passing state and configuration from the first node in a chain to the last.
class Router:
    def __init__(self, chain, *pargs, **kargs):
        # Don't use super() here because the mixins can (and generally will) override __setattr__.
        object.__setattr__(self, '___chain___', RouterChain() if chain is None else chain)
        super().__init__(*pargs, **kargs)

#---------------------------------------------------------------------------------------------------
# Used for representing an iterable group of nodes of the same type. Operations on the group are
# applied successively to each node contained in the group. The order of iteration over the nodes in
# a group is determined by each operation type's iterator. Rather than appying the operations and
# caching the results in a list on each application, the operations themselves are linked into a
# and attached to the proxy. This way, iteration over a group produces the nodes on demand.
class RouterGroup(Router):
    def __len__(self):
        return len(self.___chain___)

    def __iter__(self):
        return self.___chain___.iter_proxy(self, False)

    def __reversed__(self):
        return self.___chain___.iter_proxy(self, True)

#---------------------------------------------------------------------------------------------------
class RouterChain:
    def __init__(self, *ops):
        # The operations on the chain are applied successively from first to last. Each application
        # produces a single node, which is then passed as the input to the next operation on the
        # chain. The node returned by the last operation is the result yielded when iterating on a
        # chain. The intermediate nodes are never yielded during iteration.
        self.ops = tuple(ops)

        # The length of a chain is interpreted as the total number of nodes it can produce, not the
        # number of operations on the chain. This distinction is due to the fact that iteration on a
        # chain yields nodes, not operations. Note that a chain consisting of one or more operations
        # may produce an empty set of nodes if at least one of the operations covers an empty range.
        self.length = functools.reduce(lambda res, op: res * op.length, ops, 1) if ops else 0

    @property
    def is_group(self):
        return len(self.ops) > 0

    def extend(self, *ops):
        return type(self)(*self.ops, *ops)

    def pop(self):
        self.ops = self.ops[:-1]

    def __len__(self):
        return self.length

    def __iter__(self):
        return RouterChainIterator(self, False)

    def __reversed__(self):
        return RouterChainIterator(self, True)

    def iter_proxy(self, proxy, reversed_):
        # Create and start an iterator on the chain.
        chain_iter = reversed(self) if reversed_ else iter(self)

        # Serve the nodes produced by the chain and wrap them in an appropriate proxy.
        ctx = proxy.___context___
        for node in chain_iter:
            yield ctx.new_proxy(node, None)

#---------------------------------------------------------------------------------------------------
class RouterChainIterator:
    def __init__(self, chain, reversed_):
        self._ops = chain.ops
        self._reversed = reversed_

        # Setup for iterating over the chain of operations.
        if chain.length > 0:
            self._iters = [None] * len(chain.ops)
            self._cursor = 0
        else:
            # Handle an empty range.
            self._cursor = -1

    def __iter__(self):
        # Iterators are consumable, so no need to handle restarting.
        return self

    def __next__(self):
        cursor = self._cursor

        # The iterator has been exhausted.
        if cursor < 0:
            raise StopIteration

        # Produce the next node by successively applying each operation on the chain to the node
        # produced by the previous one. This effectively creates an unrolled call-chain along the
        # lines of: node = op[n-1].apply(op[n-2].apply(...op[1].apply(op[0].apply(None))))
        ops = self._ops
        nops = len(ops)
        iters = self._iters
        node = None
        while cursor < nops:
            # Start the next operation's iterator on the current node.
            if iters[cursor] is None:
                iters[cursor] = ops[cursor].apply(node, self._reversed)

            # Retrieve the next node from the operation.
            try:
                node = next(iters[cursor])
            except StopIteration:
                # The current operation has been exhausted.
                iters[cursor] = None

                # Setup to advance the preceeding operation on the chain.
                cursor -= 1

                # The the entire chain has been exhausted.
                if cursor < 0:
                    self._cursor = -1 # In case next() is called afterwards.
                    raise
            else:
                # Apply the remaining operations on the chain until reaching the end.
                cursor += 1

        # Start the next iteration cycle at the last operation on the chain until it's iterator is
        # exhausted, at which point the preceeding operation will be advanced.
        self._cursor = cursor - 1

        return node

#---------------------------------------------------------------------------------------------------
class RouterChainOp:
    def __init__(self, node, length):
        self.node = node
        self.length = length

    def apply(self, node=None, reversed_=False):
        raise NotImplementedError

#---------------------------------------------------------------------------------------------------
class GetattrChainOp(RouterChainOp):
    def __init__(self, node, name):
        super().__init__(node, 1)
        self.name = name

    def apply(self, node=None, reversed_=False):
        if node is None:
            node = self.node # This operation is first on the chain.

        # Retrieve the attribute from the node's spec.
        yield meta.data_get(getattr(node.spec, self.name))

#---------------------------------------------------------------------------------------------------
class GetitemChainOp(RouterChainOp):
    def __init__(self, node, key):
        super().__init__(node, key.length)
        self.key = key

    def apply(self, node=None, reversed_=False):
        if node is None:
            node = self.node # This operation is first on the chain.

        # Retrieve a child node for every index within the key's range.
        for ordinal in self.key.iter_ordinal(reversed_):
            yield node.children[ordinal]

#---------------------------------------------------------------------------------------------------
class EmptyDir:
    def __dir__(self):
        return ()

#---------------------------------------------------------------------------------------------------
class ByMemberDir:
    def __dir__(self):
        return self.___node___.members_map.keys()

#---------------------------------------------------------------------------------------------------
class BySpecGetattr:
    def __getattr__(self, name):
        node = self.___node___
        chain = self.___chain___

        # Perform the lookup.
        spec = getattr(node.spec, name)

        # Push this operation onto the end of the current chain. This is only needed when routing on
        # a group (since getattr is singular and doesn't produce a group).
        if chain.is_group:
            chain = chain.extend(GetattrChainOp(node, name))

        # Chain to a router on the retrieved specification object.
        return self.___context___.new_proxy(meta.data_get(spec), chain)

#---------------------------------------------------------------------------------------------------
class ByMemberGetattr(BySpecGetattr):
    def __getattr__(self, name):
        # Restrict the attribute name to members only.
        # TODO: Support symbol visibility concept: public (default), hidden and transparent
        node = self.___node___
        if name not in node.members_map:
            raise AttributeError(f'Attribute {name!r} is not a member name of {node.spec!r}.')

        # Perform the lookup.
        return super().__getattr__(name)

#---------------------------------------------------------------------------------------------------
class ByMemberGetitem:
    def __getitem__(self, key):
        # Perform the lookup. Key validation and slicing is left to the standard tuple().
        member = self.___node___.members[key]

        # Chain to the router on the retrieved specification object(s).
        if isinstance(member, collections.abc.Sequence):
            # Index is a slice.
            # TODO: Make this a container/iterator object instead of a list.
            return [
                self.___context___.new_proxy(meta.data_get(m.value), self.___chain___)
                for m in member
            ]

        # Index is singular.
        return self.___context___.new_proxy(meta.data_get(member.value), self.___chain___)

    def __len__(self):
        return len(self.___node___.members)

#---------------------------------------------------------------------------------------------------
# Indexing formats:
# - Refer to https://docs.python.org/3/reference/datamodel.html#sequences
# - Uni-dimensional indexing.
#   - Selecting a singular item:
#     - x[i]  => Item in sequence x with index i.
#     - x[-i] => Item in sequence x with index len(x) - i.
#   - Selecting a range of items:
#     - x[i:j]   => Range of items in sequence x with index k such that i <= k < j.
#     - x[i:j:s] => Range of items in sequence x with index k such that i <= k < j with step size s.
#     - x[i,j]   => Pair of items in sequence x. Equivalent to the following sequence of single
#                   indexing operations: x[i], x[j]. This style uses Python's slice list syntax. Any
#                   number of items can be separated by commas, in any combination of single numbers
#                   or slices (such as x[i,j:k,m:n,p,q], where i, p and q are single numbers and j:k
#                   and m:n are slices). This syntax allows for arbitrary postioning and re-ordering
#                   of the items, potentially creating an iteration of length greater than the
#                   sequence itself (which of course implies that items are replicated since the
#                   number of items is fixed at the time of indexing).
# - Multi-dimensional indexing relies on repeated applications of the indexing operator. A complete
#   key is built-up over each application. Between applications, the missing fields in the key are
#   padded out with slices covering the entire range. For 2D x[M][N], x[i] is equivalent to x[i][:],
#   until the second indexing operation is applied such that (x[i])[j] (or y=x[i] then y[j]).
#   - Selecting a singular item:
#     - x[i][j] => Singular item in multi-dimensional array x.
#   - Selecting a range of items:
#     - x[i:j][k]       => Range of items in multi-dimensional array x. Selects rows i to j-1 in the
#                          k-th column.
#     - x[i,j:k][m:n,p] => Range of items in multi-dimensional array x. Selects rows i and j to k-1
#                          across the m to n-1 and p-th columns.
#---------------------------------------------------------------------------------------------------
class ByIndexGetitem:
    def __init__(self, *pargs, key=None, **kargs):
        super().__init__(*pargs, **kargs)

        # Attach the current partial key for handling repeated indexing operations.
        # Don't use super() here because the mixins can (and generally will) override __setattr__.
        object.__setattr__(self, '___key___', key)

    def __getitem__(self, key):
        node = self.___node___
        chain = self.___chain___
        partial_key = self.___key___

        # Build-up the key from repeated applications of proxy[key], one application per dimension.
        # The key is wrapped in a tuple to indicate that it encompasses a single field. This is to
        # support the slice list syntax, since a slice list represents a range built from multiple
        # sub-ranges.
        if partial_key is None:
            # First application.
            partial_key = node.indexer.new_key(())
        else:
            # Remove the previous chain operation on the wildcarded partial key in preparation for
            # replacing it with a new one containing the key extension from this application.
            chain.pop()
        new_key = partial_key.extend((key,))

        # Push this operation onto the end of the current chain. Since operations only need to be
        # tracked when routing through a group, a new operation needs to be added to the chain if
        # the new key creates a group (due to being a slice) or is already in a group.
        if new_key.is_slice or chain.is_group:
            chain = chain.extend(GetitemChainOp(node, new_key))

        # The newly assembled key is partial. Create a new router on the current node to continue
        # partial indexing operations until the key is completed. The range of iterable items for
        # the new proxy will differ based on the ranges specified by the key extension.
        if new_key.is_partial:
            return self.___context___.new_proxy(node, chain, key=new_key)

        # A complete key has been assembled.
        # When routing for a slice, the first child node is used as the reference object. This node
        # only provides type information. Selecting it doesn't imply that it's actually included in
        # the range covered by the slice. This is done to handle empty slice ranges.
        child = node.children[0 if new_key.is_slice else new_key.to_ordinal(new_key.first)]

        # Chain to the router of the retrieved specification object.
        return self.___context___.new_proxy(child, chain)

#---------------------------------------------------------------------------------------------------
class ByRegisterGetitem:
    def __getitem__(self, key):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

#---------------------------------------------------------------------------------------------------
class ByWordGetitem:
    def __getitem__(self, key):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

#---------------------------------------------------------------------------------------------------
class ByAddressGetitem:
    def __getitem__(self, key):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

#---------------------------------------------------------------------------------------------------
# Routing by path consists of:
# - Attribute name lookups routed through a node's member namespace.
class ByPathName(Router, ByMemberDir, ByMemberGetattr): ...
class ByPathNameGroup(RouterGroup, ByMemberDir, ByMemberGetattr): ...
# - Numeric tuple (multi-dimensional) indexing routed through a sequence node.
class ByPathIndex(Router, EmptyDir, ByIndexGetitem): ... # Non-iterable indexing.
class ByPathIndexGroup(RouterGroup, EmptyDir, ByIndexGetitem): ... # Iterable indexing.

# Routing by slot consists of:
# - Numeric indexing routed through a node's member table.
class BySlotMember(Router, EmptyDir, ByMemberGetitem): ...
# - Numeric tuple (multi-dimensional) indexing routed through a sequence node.
class BySlotIndex(Router, EmptyDir, ByIndexGetitem): ...

# Routing by register consists of:
# - Numeric indexing routed through a virtual sequence of registers.
class ByRegister(Router, EmptyDir, ByRegisterGetitem): ...

# Routing by word consists of:
# - Numeric indexing routed through a virtual sequence of data words.
class ByWord(Router, EmptyDir, ByWordGetitem): ...

# Routing by address consists of:
# - Numeric indexing routed through a virtual sequence of address cells.
class ByAddress(Router, EmptyDir, ByAddressGetitem): ...
