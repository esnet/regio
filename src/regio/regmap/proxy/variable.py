#---------------------------------------------------------------------------------------------------
__all__ = ()

from ..io import io
from ..spec import address, array, field, register, structure, union

#---------------------------------------------------------------------------------------------------
class Variable:
    def __init__(self, node, ctx, initializer=None, *pargs, **kargs):
        super().__init__()

        self._node = node
        self._pargs = pargs
        self._kargs = kargs

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
        self.proxy = self._context.new_proxy(node)

    def load(self, initializer=None):
        # Pass the default value down to the IO buffer for use during buffered reads.
        if isinstance(initializer, int):
            self._context.io.default = initializer
            return

        # TODO: Should support a dict/list of path names to allow providing different initializers
        #       for the various objects in the sub-tree (like C-style structure initialization).
        if initializer is not None:
            raise ValueError(f'Unknown initializer {initializer!r}. Must be None or an int.')

        # Perform low-level IO to read all registers.
        load_region = self._context.io.load_region

        # The variable's node is itself a register.
        if self._node.region.register is not None:
            load_region(self._node.region)
            return

        # The variable is a container, so load all nested registers.
        # TODO: Don't walk the whole sub-tree. No need to walk past a register node.
        for node in self._node.descendants:
            if node.region.register is not None:
                load_region(node.region)

    def store(self, initializer=None):
        # Write all buffered data.
        if initializer is None:
            self.sync()
            return

        # TODO: Should support a dict/list of path names to allow providing different initializers
        #       for the various objects in the sub-tree (like C-style structure initialization).
        if not isinstance(initializer, int):
            raise ValueError(f'Unknown initializer {initializer!r}. Must be None or an int.')

        # Perform low-level IO to write all registers.
        store_region = self._context.io.store_region

        # The variable's node is itself a register.
        if self._node.region.register is not None:
            store_region(self._node.region, initializer)
            return

        # The variable is a container, so store all nested registers.
        # TODO: Don't walk the whole sub-tree. No need to walk past a register node.
        for node in self._node.descendants:
            if node.region.register is not None:
                store_region(node.region, initializer)

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
            'qualname': 'Path',
            'range': 'Range',
            'value_hex': 'Value',
            'value_bits': 'Value',
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

        # Add data for the heading labels and the variable.
        row_data = [
            update_widths(headings),
            update_widths(units),
            update_widths(self._format_node(helper)),
        ]

        # Gather data for each node in the variable's sub-tree.
        for node in self._node.descendants:
            var = self._context.new_variable(node, ...)
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
        # Figure out how to display the qualified names of all the nodes.
        for kargs in (var._kargs, var._context.kargs):
            base = kargs.get('qualname_base')
            if base is not None:
                self.qualname_stem, self.qualname_start = base
                break
        else:
            self.qualname_stem, self.qualname_start = None, 0

        # Determine the maximum number of nibbles for consistent offset display.
        region = var._node.region
        self.offset_units = 'Bytes' # TODO: Get from low-level IO.
        self.offset_scale = region.data_width // 8 # TODO: Get from low-level IO.
        self.offset_nibbles = ((region.size * self.offset_scale).bit_length() + 4 - 1) // 4

    def qualname(self, node):
        qualname = node.qualname_from(self.qualname_start)
        if self.qualname_stem is None:
            return qualname
        if not qualname:
            return self.qualname_stem + f' [=> {node.qualname}]'
        return self.qualname_stem + '.' + qualname

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
