#---------------------------------------------------------------------------------------------------
__all__ = ()

from ..io import io
from ..spec import address, array, field, register, structure, union

#---------------------------------------------------------------------------------------------------
class Variable:
    def __init__(self, node, ctx, chain, initializer=None, *pargs, **kargs):
        super().__init__()

        self._node = node
        self._chain = chain
        self._pargs = tuple(pargs)
        self._kargs = dict(kargs)

        # New variables are created either by using the context directly (by reference) or on a
        # buffered copy of it (by value).
        if initializer is Ellipsis:
            # By reference.
            self._context = ctx
        else:
            # By value.
            # If the context is already buffered, pull-out it's low-level IO for the buffering.
            # TODO: Should be able to use a custom buffer based on array.array(), where the index
            #       is the register ordinal, adjusted for the first register in the sub-tree (all
            #       registers in the sub-tree will be in a contiguous ordinal range).
            llio = ctx.io.llio if isinstance(ctx.io, io.BufferedIO) else ctx.io
            self._context = ctx.copy(io.BufferedIO(llio))
            self.load(initializer)

        # Setup a proxy for the variable on the initialized context.
        self.proxy = self._context.new_proxy(node, chain)

    def load(self, initializer=None):
        # Pass the default value down to the IO buffer for use during buffered reads.
        if isinstance(initializer, int):
            self._context.io.default = initializer
            return

        # TODO: Should support a dict/list of path names to allow providing different initializers
        #       for the various objects in the sub-tree (like C-style structure initialization).
        if initializer is not None:
            raise ValueError(f'Unknown initializer {initializer!r}. Must be None or an int.')

        # The variable was created on a singular node, load all registers in it's hierarchy.
        if not self._chain.is_group:
            self._load_node(self._node)
            return

        # The variable was created on a node group, load all registers in the hierarchy of every
        # node in the group.
        for node in self._chain:
            self._load_node(node)

    def _load_node(self, node):
        # Perform low-level IO to read all registers.
        load_region = self._context.io.load_region

        # The node is itself a register.
        if node.region.register is not None:
            load_region(node.region)
            return

        # The node is a container, so load all registers in it's hierarchy.
        # TODO: Don't walk the whole sub-tree. No need to walk past a register node.
        for child in node.descendants:
            if child.region.register is not None:
                load_region(child.region)

    def store(self, initializer=None):
        # Write all buffered data.
        if initializer is None:
            self.sync()
            return

        # TODO: Should support a dict/list of path names to allow providing different initializers
        #       for the various objects in the sub-tree (like C-style structure initialization).
        if not isinstance(initializer, int):
            raise ValueError(f'Unknown initializer {initializer!r}. Must be None or an int.')

        # The variable was created on a singular node, store all registers in it's hierarchy.
        if not self._chain.is_group:
            self._store_node(self._node, initializer)
            return

        # The variable was created on a node group, store all registers in the hierarchy of every
        # node in the group.
        for node in self._chain:
            self._store_node(node, initializer)

    def _store_node(self, node, initializer):
        # Perform low-level IO to write all registers.
        store_region = self._context.io.store_region

        # The node is itself a register.
        if node.region.register is not None:
            store_region(node.region, initializer)
            return

        # The node is a container, so store all registers in it's hierarchy.
        # TODO: Don't walk the whole sub-tree. No need to walk past a register node.
        for child in node.descendants:
            if child.region.register is not None:
                store_region(child.region, initializer)

    def sync(self):
        self._context.io.sync()

    def drop(self):
        self._context.io.drop()

    def flush(self):
        self._context.io.flush()

    def __str__(self):
        headings = {
            'type': 'Type',
            'size': 'Size',
            'offset': 'Offset',
            'range': 'Range',
            'value_hex': 'Value',
            'value_bits': 'Value',
            'qualname': 'Path',
        }
        fmt = '{type:>{wtype}}'
        fmt += ' | {size:>{wsize}}'
        fmt += ' | {offset:>{woffset}}'
        fmt += ' | {range:^{wrange}}'
        fmt += '{value_hex:<{wvalue_hex}}'
        fmt += ' : {value_bits:<{wvalue_bits}}'
        fmt += ' | {qualname:<{wqualname}}'

        widths = {}
        hnames = set(headings)
        def update_widths(data):
            k = 'value_hex'
            if k in data:
                data[k] = ' = ' + data[k]

            k = 'value_bits'
            if k in data:
                data[k] = data[k]

            data.update((hn, '') for hn in hnames.difference(data))

            for k, v in data.items():
                wk = f'w{k}'
                widths[wk] = max(len(v), widths.get(wk, 0))
            return data

        # Setup a helper for consistent formatting of each node.
        helper = FormatHelper(self)
        offset_units = f'({helper.offset_units})'
        units = {
            'size': offset_units,
            'offset': offset_units,
            'value_hex': '(Hex)',
            'value_bits': '(Bits)',
        }

        # Insert the mapping between the stem and root names into the header.
        if helper.qualstem is not None:
            units['qualname'] = f'({helper.qualstem} => {helper.qualroot})'

        # Add formatting data for the heading labels and the variable.
        row_data = [
            update_widths(headings),
            update_widths(units),
        ]

        # Determine the set of nodes to be formatted.
        if self._chain.is_group:
            # The variable was created on a node group.
            nodes = self._chain
        else:
            # The variable was created on a singular node.
            nodes = (self._node,)

        # Gather formatting data for all nodes in the variable's hierarchy.
        for node in nodes:
            # Format the node.
            var = self if node is self._node else self._context.new_variable(node, None, ...)
            row_data.append(update_widths(var._format_node(helper)))

            # Gather formatting data for each child node in the hierarchy.
            for child in node.descendants:
                var = self._context.new_variable(child, None, ...)
                row_data.append(update_widths(var._format_node(helper)))

        # Generate a string for each row.
        width = 0
        rows = []
        for data in row_data:
            row = fmt.format(**data, **widths)
            width = max(width, len(row))
            rows.append(row)

        # Setup heading separators to frame the row strings.
        sep = '-' * width
        rows.insert(0, '=' * width)
        rows.insert(3, sep)
        rows.append(sep)

        return '\n'.join(rows)

#---------------------------------------------------------------------------------------------------
class FormatHelper:
    def __init__(self, var):
        self.root = var._node
        self.is_group = var._chain.is_group

        # Figure out how to display the qualified names of all the nodes.
        self.abspath = False
        self.qualstem, self.qualroot, self.qualstart = None, None, 0
        for kargs in (var._context.kargs, var._kargs):
            abspath = kargs.get('abspath')
            if abspath is not None:
                self.abspath = abspath

            qualbase = kargs.get('qualbase')
            if qualbase is not None:
                self.qualstem, self.qualroot, self.qualstart = qualbase

        # Determine the maximum number of nibbles for consistent offset display.
        region = var._node.region
        self.offset_units = 'Bytes' # TODO: Get from low-level IO.
        self.offset_scale = region.data_width // 8 # TODO: Get from low-level IO.
        self.offset_nibbles = ((region.size * self.offset_scale).bit_length() + 4 - 1) // 4

    def abs_qualname(self, node):
        qualname = node.qualname_from(self.qualstart)
        if self.qualstem is None:
            return qualname
        return self.qualstem + ('.' + qualname if qualname else '')

    def rel_qualname(self, node):
        if not self.is_group and node is self.root:
            return f'. [=> {self.abs_qualname(node)}]'
        return '.' + node.qualname_from(len(self.root.path))

    def qualname(self, node):
        return self.abs_qualname(node) if self.abspath else self.rel_qualname(node)

    def size(self, value):
        value *= self.offset_scale
        return f'{value:,}'

    def offset(self, value):
        value *= self.offset_scale
        return f'0x{value:0{self.offset_nibbles}x}'

    def offset_range(self, start, end):
        return self.offset(start) + ' - ' + self.offset(end)

    def value_hex(self, value, region):
        return f'0x{value:0{region.nibbles}x}'

    def value_bits(self, value, region):
        return f'0b{value:0{region.width}_b}'

#---------------------------------------------------------------------------------------------------
class StructureFormatter:
    def _format_node(self, helper):
        ntype = type(self._node)
        if ntype is address.Node:
            type_ = 'Address Space'
        elif ntype is array.ElementNode:
            type_ = 'Array Element'
        elif ntype is structure.Node:
            type_ = 'Structure'
        elif ntype is union.Node:
            type_ = 'Union'
        else:
            raise TypeError(f'Unknown node type {ntype!r}.')

        region = self._node.region
        start = region.offset.absolute
        end = region.offset.absolute + region.size - 1

        return {
            'type': type_,
            'qualname': helper.qualname(self._node),
            'size': helper.size(region.size),
            'offset': helper.offset_range(start, end),
        }

#---------------------------------------------------------------------------------------------------
class ArrayFormatter:
    def _format_node(self, helper):
        region = self._node.region
        start = region.offset.absolute
        end = region.offset.absolute + region.size - 1
        qualname = helper.qualname(self._node)

        return {
            'type': 'Array',
            'qualname': f'{qualname}{[*self._node.indexer.fields]}',
            'size': helper.size(region.size),
            'offset': helper.offset_range(start, end),
        }

#---------------------------------------------------------------------------------------------------
class RegisterFormatter:
    def _format_node(self, helper):
        region = self._node.region
        value = int(self.proxy)

        return {
            'type': 'Register',
            'qualname': helper.qualname(self._node),
            'size': helper.size(region.size),
            'offset': helper.offset(region.offset.absolute),
            'value_hex': helper.value_hex(value, region),
        }

#---------------------------------------------------------------------------------------------------
class FieldFormatter:
    def _format_node(self, helper):
        region = self._node.region
        value = int(self.proxy)

        range_ = f'{region.pos.absolute}'
        if region.width > 1:
            end = region.pos.absolute + region.width - 1
            range_ = f'{end}:' + range_

        return {
            'type': 'Field',
            'qualname': helper.qualname(self._node),
            'range': f'[{range_}]',
            'value_hex': helper.value_hex(value, region),
            'value_bits': helper.value_bits(value, region),
        }

#---------------------------------------------------------------------------------------------------
class StructureVariable(Variable, StructureFormatter): ...
class ArrayVariable(Variable, ArrayFormatter): ...
class RegisterVariable(Variable, RegisterFormatter): ...
class FieldVariable(Variable, FieldFormatter): ...
