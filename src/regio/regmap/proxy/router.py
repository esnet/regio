#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc

from ..spec import meta

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
        # Perform the lookup.
        spec = getattr(self.___node___.spec, name)

        # Chain to a router on the retrieved specification object.
        return self.___context___.new_proxy(meta.data_get(spec))

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
            return [self.___context___.new_proxy(meta.data_get(m.value)) for m in member]

        # Index is singular.
        return self.___context___.new_proxy(meta.data_get(member.value))

    def __len__(self):
        return len(self.___node___.members)

#---------------------------------------------------------------------------------------------------
# Indexing formats:
# - Refer to https://docs.python.org/3/reference/datamodel.html#sequences
# - Uni-dimensional indexing.
#   - Selecting a singular item:
#     - x[i] => item in sequence x with index i.
#     - x[-i] => item in sequence x with index len(x) - i.
#   - Selecting a range of items:
#     - x[i:j] => range of items in sequence x with index k such that i <= k < j.
#     - x[i:j:s] => range of items in sequence x with index k such that i <= k < j using step size s.
# - Multi-dimensional indexing via Python's slice list syntax. Each field in the list is interpreted
#   as an index for a single dimension (as with C-style arrays).
#   - Selecting a singular item:
#     - x[i,j] => singular item in multi-dimensional array x. Equivalent to the following sequence of
#                 single indexing operations: x[i][j].
#   - Selecting a range of items:
#     - x[i:j,k] => range of items in multi-dimensional array x. Equivalent to the following sequence
#                   of single indexing operations: x[i:j][k].
#   - Repeated applications of the indexing operation will build a key by accumulating a sequence of
#     partial keys. This allows x[i,j] to be used in steps as y = x[i], then y[j].
#---------------------------------------------------------------------------------------------------
class ByIndexGetitem:
    def __init__(self, *pargs, key=None, **kargs):
        super().__init__(*pargs, **kargs)

        # Attach the current partial key for handling repeated indexing operations.
        # Don't use super() here because the mixins can override __setattr__.
        key = self.___node___.indexer.new_key(()) if key is None else key
        object.__setattr__(self, '___key___', key)

    def __getitem__(self, key):
        # Build-up the key from one or more applications of router[key].
        key = self.___key___.extend(key)

        # Short-circuit check for empty ranges.
        if key.length < 1:
            return ()

        # A partial key has been assembled. Create a new router to continue partial indexing
        # operations until the key is completed.
        if key.nfields < key.indexer.nfields:
            return self.___context___.new_proxy(node, key=key)

        # A complete key has been assembled.
        if key.length > 1:
            # Key is a slice. Create a routing container to handle retrieving the items.
            return ByIndexSlice(self, key)

        # Index is singular.
        node = self.___node___.children[key.to_ordinal(key.start)]

        # Chain to the router of the retrieved specification object.
        return self.___context___.new_proxy(node)

    def __len__(self):
        return len(self.___node___.children)

#---------------------------------------------------------------------------------------------------
# TODO: Support routing on each item in the sequence (since the items are of the same type).
class ByIndexSlice:
    def __init__(self, proxy, key, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self._node = proxy.___node___
        self._context = proxy.___context___
        self._key = key

    def __iter__(self):
        return ByIndexSliceIterator(self, False)

    def __reversed__(self):
        return ByIndexSliceIterator(self, True)

    def __len__(self):
        return self._key.length

#---------------------------------------------------------------------------------------------------
class ByIndexSliceIterator:
    def __init__(self, slice_, reversed_):
        self._slice = slice_

        # Start the key's iterator.
        iter_fn = reversed if reversed_ else iter
        self._key_iter = iter_fn(slice_._key)

    def __iter__(self):
        # Iterators are consumable, so no need to handle restarting.
        return self

    def __next__(self):
        # Get the next index within the key's range.
        index = next(self._key_iter)

        # Perform the lookup.
        node = self._slice._node.children[self._slice._key.to_ordinal(index)]

        # Chain to the router of the retrieved node.
        return self._slice._context.new_proxy(node)

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
class ByPathName(ByMemberDir, ByMemberGetattr): ...
# - Numeric tuple (multi-dimensional) indexing routed through a sequence node.
class ByPathIndex(EmptyDir, ByIndexGetitem): ...

# Routing by slot consists of:
# - Numeric indexing routed through a node's member table.
class BySlotMember(EmptyDir, ByMemberGetitem): ...
# - Numeric tuple (multi-dimensional) indexing routed through a sequence node.
class BySlotIndex(EmptyDir, ByIndexGetitem): ...

# Routing by register consists of:
# - Numeric indexing routed through a virtual sequence of registers.
class ByRegister(EmptyDir, ByRegisterGetitem): ...

# Routing by word consists of:
# - Numeric indexing routed through a virtual sequence of data words.
class ByWord(EmptyDir, ByWordGetitem): ...

# Routing by address consists of:
# - Numeric indexing routed through a virtual sequence of address cells.
class ByAddress(EmptyDir, ByAddressGetitem): ...
