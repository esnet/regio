#---------------------------------------------------------------------------------------------------
__all__ = ()

import enum

from . import field, meta, tree
from ..types import config

#---------------------------------------------------------------------------------------------------
class Config(config.Config):
    access = config.EnumFromStr(field.Access, 'RW')
    align = config.PositiveInt(1)
    offset = config.PositiveInt(0)
    size = config.PositiveInt(1)

#---------------------------------------------------------------------------------------------------
# Meta-data attached to instances.
class Node(tree.Node):
    def init_region(self, region):
        # A register can only be defined within a word counting region.
        if not region.in_words:
            raise AssertionError(
                f'Register {self.spec!r} is misplaced in the regmap specification. Make sure that '
                'the location is within a word counting region.')

        # Set the base offset in the outer region.
        if self.config.offset > 0:
            region.goto(self.config.offset)

        # Make sure the offset is properly aligned in the outer region.
        region.align(self.config.align)

        # Mark the inner region's beginning.
        region.begin()

        # Add sub-regions for the register members. The counting units are changed from data words
        # to bits for the duration and restored afterwards.
        region.begin_bits()
        for node in self.children:
            region.add(node)
        region.end_bits()

        # Determine the inner region's size.
        size = self.config.size
        if region.size < 1:
            # If the register has no sub-structure to occupy any bits, use the configured default.
            region.inc(size)
        elif region.size < size:
            # Pad out the inner region.
            region.inc(size - region.size)

        # Finalize the inner region.
        region.end()

#---------------------------------------------------------------------------------------------------
class Register(meta.Object, metainfo=(Config, Node)): ...
