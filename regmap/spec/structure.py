#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import meta, tree
from ..types import config

#---------------------------------------------------------------------------------------------------
class Config(config.Config):
    align = config.PositiveInt(1)
    offset = config.PositiveInt(0)
    pad = config.PositiveInt(0)
    pad_to = config.PositiveInt(0)

#---------------------------------------------------------------------------------------------------
# Meta-data attached to instances.
class Node(tree.Node):
    def init_region(self, region):
        # Set the base offset in the outer region.
        if self.config.offset > 0:
            region.goto(self.config.offset)

        # Make sure the offset is properly aligned in the outer region.
        region.align(self.config.align)

        # Mark the inner region's beginning.
        region.begin()

        # Add sub-regions for the structure members.
        for node in self.children:
            region.add(node)

        # Pad out the inner region.
        region.inc(self.config.pad)
        if region.size < self.config.pad_to:
            region.inc(self.config.pad_to - region.size)

        # Finalize the inner region.
        region.end()

#---------------------------------------------------------------------------------------------------
class Structure(meta.Object, metainfo=(Config, Node)): ...
