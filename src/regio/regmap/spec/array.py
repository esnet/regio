#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import meta, structure, tree
from ..types import config, indexing

#---------------------------------------------------------------------------------------------------
class Config(config.Config):
    # Array configuration.
    align = config.PositiveInt(1)
    dimensions = config.PositiveIntSequence()
    offset = config.PositiveInt(0)
    pad = config.PositiveInt(0)
    pad_to = config.PositiveInt(0)

    # Per-element configuration.
    # TODO: Need a descriptor for redirecting to a sub-config? Should be something like:
    #       element = config.SubConfig(structure.Config())
    element_align = config.PositiveInt(1)
    element_pad = config.PositiveInt(0)
    element_pad_to = config.PositiveInt(0)

#---------------------------------------------------------------------------------------------------
# Meta-data attached to instances.
class Node(tree.Node):
    def members_init(self):
        # Setup an indexer for sorting mutli-dimensional index tuples and mapping them to an ordinal
        # in the manner of C-style arrays.
        self.indexer = indexing.CArrayIndexer(self.config.dimensions)

        # Instantiate each element in the array. The resulting nodes will be added as children
        # according to the ordering dictated by the indexer (as a flattened C-style array).
        data = meta.data_get(type(self.spec))
        for index in self.indexer:
            data.element_cls(f'{self.name}{[*index]}', self.spec, index)

    def init_region(self, region):
        # Set the base offset in the outer region.
        if self.config.offset > 0:
            region.goto(self.config.offset)

        # Make sure the offset is properly aligned in the outer region.
        region.align(self.config.align)

        # Mark the inner region's beginning.
        region.begin()

        # Add sub-regions for the array elements.
        for node in self.children:
            region.add(node)

        # Pad out the inner region. Note that this is only padding the end of the entire array.
        region.inc(self.config.pad)
        if region.size < self.config.pad_to:
            region.inc(self.config.pad_to - region.size)

        # Finalize the inner region.
        region.end()

#---------------------------------------------------------------------------------------------------
# TODO: Implement __repr__ to print out the class and the configuration it was defined with.
class Array(meta.Object, metainfo=(Config, Node)):
    def __init_subclass__(cls, **kargs):
        super().__init_subclass__(**kargs)

        # The sub-class is not actually an Array, just inheriting the members from one.
        data = meta.data_get(cls)
        if data.node_cls is not Node:
            return

        # Extract the per-element configuration data to be passed along to each element instance.
        prefix = 'element_'
        config_kargs = dict(
            (k[len(prefix):], v)
            for k, v in data.config.changed_map.items()
            if k.startswith(prefix)
        )

        # Transfer the members to the element's namespace. Note that order doesn't matter here
        # because the members tuple already captures the correct ordering.
        class Namespace(dict): ...
        ns = Namespace((m.name, m.value) for m in data.members)
        ns.members = tuple(data.members)

        # Create a structure to contain the members for array element.
        # TODO: How to set the module of the generated element class to match the array class?
        data.element_cls = type(cls.__name__ + '_element', (Element,), ns, **config_kargs)

#---------------------------------------------------------------------------------------------------
# Meta-data attached to element instances.
class ElementNode(structure.Node):
    def __init__(self, spec, members, config, index, *pargs, **kargs):
        super().__init__(spec, members, config, *pargs, **kargs)
        self.index = index

    def members_init(self):
        self.ordinal = self.parent.indexer.to_ordinal(self.index)
        self.path = self.parent.path[:-1] + (self.name,)

        super().members_init()

# Should not be explicitly sub-classed. Used implicitly in Array __init_subclass__.
class Element(structure.Structure, metainfo=(structure.Config, ElementNode)): ...
