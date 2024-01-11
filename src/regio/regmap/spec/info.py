#---------------------------------------------------------------------------------------------------
__all__ = (
    'address_of',
    'config_of',
    'data_width_of',
    'octets_of',
    'offset_of',
    'oid_of',
    'ordinal_of',
    'region_of',
    'size_of',
)

import collections.abc

from . import meta

#---------------------------------------------------------------------------------------------------
def _node_from_index(spec, index):
    node = meta.data_get(spec)
    if index is not None:
        if isinstance(index, collections.abc.Sequence):
            index = node.indexer.to_ordinal(index)
        node = node.children[index]
    return node

#---------------------------------------------------------------------------------------------------
def region_of(spec, index=None):
    return _node_from_index(spec, index).region

#---------------------------------------------------------------------------------------------------
# In data words.
def address_of(spec, index=None):
    return region_of(spec, index).offset.absolute

#---------------------------------------------------------------------------------------------------
def config_of(spec, index=None):
    return _node_from_index(spec, index).config

#---------------------------------------------------------------------------------------------------
def data_width_of(spec, index=None):
    return region_of(spec, index).data_width

#---------------------------------------------------------------------------------------------------
def octets_of(spec, index=None):
    return region_of(spec, index).octets

#---------------------------------------------------------------------------------------------------
# In data words.
def offset_of(spec, index=None):
    return region_of(spec, index).offset.relative

#---------------------------------------------------------------------------------------------------
def oid_of(spec, index=None):
    return region_of(spec, index).oid

#---------------------------------------------------------------------------------------------------
def ordinal_of(spec, index=None):
    return region_of(spec, index).ordinal

#---------------------------------------------------------------------------------------------------
# In data words.
def size_of(spec, index=None):
    return region_of(spec, index).size
