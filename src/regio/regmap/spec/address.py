#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import counting, meta, tree
from ..types import config

#---------------------------------------------------------------------------------------------------
class Config(config.Config):
    align = config.PositiveInt(1)
    data_width = config.PositiveInt()
    domain_class = config.SubClass(counting.Domain)
    indirect = config.Bool(False)
    offset = config.PositiveInt(0)
    pad = config.PositiveInt(0)
    pad_to = config.PositiveInt(0)

#---------------------------------------------------------------------------------------------------
# Meta-data attached to instances.
class Node(tree.Node):
    def members_init(self):
        super().members_init()

        # An address space can be either standalone or embedded into another. When embedded, the
        # parent's counting domain is used instead of creating a local one.
        if isinstance(self.parent, tree.Root):
            self.config.domain_class(self.config.data_width, self.spec)

    def init_region(self, region):
        # An address space can only be defined within a word counting region.
        if not region.in_words:
            raise AssertionError(
                f'Address space {self.spec!r} is misplaced in the regmap specification. Make sure '
                'that the location is within a word counting region.')

        # An address space always forms it's own counting (inner) region distinct from all other
        # (outer) regions since it can potentially have a different data word width. There are two
        # supported usage patterns for accessing objects in the address space:
        # - direct: The words in the inner region share the same counting space as the outer region
        #           and are accessible using the same offsets. In essence, the inner region is a
        #           continuation of the outer region, but may count using a different word width.
        # - indirect: The words in the inner region are counted independently from the outer region
        #             and are not accessible using the same offsets. In essence, the inner region
        #             forms an isolated island of it's own and does not occupy space seen by the
        #             outer region. However, the objects within the inner region will be included
        #             when assigning object IDs and ordinals to give the appearance of continuity.

        # Mark the inner region's beginning and change the data word width. This may result in a
        # re-alignment of the outer region to a joint word boundary. This ensures that the outer
        # region ends on a boundary of it's own, while the inner region starts on a boundary that
        # suits the configured width. Also,
        # - When access is direct, counting is continued from the outer region.
        # - When access is indirect, counting is reset to ensure the inner region starts at 0.
        region.begin(self.config.indirect, self.config.data_width)

        # Set the base offset in the inner region.
        if self.config.offset > 0:
            region.goto(self.config.offset)

        # Make sure the offset is properly aligned in the inner region.
        region.align(self.config.align)

        # Add the address space members.
        for node in self.children:
            region.add(node)

        # Pad out the inner region.
        region.inc(self.config.pad)
        if region.size < self.config.pad_to:
            region.inc(self.config.pad_to - region.size)

        # Finalize the inner region. This may result in a re-alignment of the outer region to a
        # joint word boundary. Also,
        # - When access is direct, the outer region is updated for the inner region's size.
        # - When access is indirect, the outer region is not updated for the inner region's size.
        region.end(not self.config.indirect)

#---------------------------------------------------------------------------------------------------
class AddressSpace(meta.Object, metainfo=(Config, Node)): ...
