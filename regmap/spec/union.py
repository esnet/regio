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

        # Add sub-regions for the union members. Each sub-region is counted independently from it's
        # peers and the final size is determined by the largest sub-region.
        size = 0
        for node in self.children:
            region.pause()
            region.add(node)
            size = max(size, region.restore())
        region.inc(size)

        # Pad out the inner region.
        region.inc(self.config.pad)
        if region.size < self.config.pad_to:
            region.inc(region.size - self.config.pad_to)

        # Finalize the inner region.
        region.end()

#---------------------------------------------------------------------------------------------------
class Union(meta.Object, metainfo=(Config, Node)): ...
