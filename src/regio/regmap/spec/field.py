#---------------------------------------------------------------------------------------------------
__all__ = ()

import enum

from . import meta, tree
from ..types import config

#---------------------------------------------------------------------------------------------------
class Access(enum.Enum):
    RO = enum.auto()
    WO = enum.auto()
    RW = enum.auto()
    WR_EVT = enum.auto()
    RD_EVT = enum.auto()

#---------------------------------------------------------------------------------------------------
class Config(config.Config):
    access = config.EnumFromStr(Access, 'RW')
    align = config.PositiveInt(1)
    offset = config.PositiveInt(0)
    width = config.PositiveInt(0)

#---------------------------------------------------------------------------------------------------
# Meta-data attached to instances.
class Node(tree.Node):
    def init_region(self, region):
        # A field can only be defined within a bit counting region.
        if not region.in_bits:
            raise AssertionError(
                f'Field {self.spec!r} is misplaced in the regmap specification. Make sure that the '
                'location is within a bit counting region.')

        # Set the base offset in the outer region.
        if self.config.offset > 0:
            region.goto(self.config.offset)

        # Make sure the offset is properly aligned in the outer region.
        region.align(self.config.align)

        # Mark the inner region's beginning.
        region.begin()

        # Add the field members.
        for node in self.children:
            region.add(node)

        # Determine the inner region's width.
        width = self.config.width
        if region.size < 1:
            # If the field has no sub-structure to occupy any bits, use the width of a single data
            # word as default unless otherwise specified via configuration.
            region.inc(region.data_width if width < 1 else width)
        elif region.size < width:
            # Pad out the inner region.
            region.inc(width - region.size)

        # Finalize the inner region.
        region.end()

#---------------------------------------------------------------------------------------------------
class Field(meta.Object, metainfo=(Config, Node)): ...
