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

    def config_get(self, key, default=None):
        for kargs in (self._kargs, self._context.kargs):
            value = kargs.get(key)
            if value is not None:
                return value
        return default

    def __str__(self):
        # Get the formatter class to use.
        name = self.config_get('formatter', 'table')
        if name not in FORMATTERS:
            choices = ' | '.join(sorted(FORMATTERS))
            raise ValueError(f'Unknown variable formatter "{name}". Must be one of: {choices}.')

        # Generate the formatted string.
        return str(FORMATTERS.get(name)(self))

#---------------------------------------------------------------------------------------------------
class Formatter:
    def __init__(self, var):
        self.var = var
        self.root = var._node
        self.is_group = var._chain.is_group

        # Capture general display configuration.
        self.verbose = var.config_get('verbose', False)

        # Determine the display format for the qualified name of all the nodes.
        self.abspath = var.config_get('abspath', False)
        self.qualstem, self.qualroot, self.qualstart = var.config_get('qualbase', (None, None, 0))

        # Sort lexicographically or leave in the order defined in the regmap specification.
        self.path_sort = self.var.config_get('path_sort', False)

        # Determine the maximum number of nibbles for consistent offset display.
        region = var._node.region
        self.offset_units = 'Bytes' # TODO: Get from low-level IO.
        self.offset_scale = region.data_width // 8 # TODO: Get from low-level IO.
        self.offset_nibbles = ((region.size * self.offset_scale).bit_length() + 4 - 1) // 4

        # Determine the formatting for values.
        self.ignore_access = var.config_get('ignore_access', False)
        self.with_hex_grouping = var.config_get('hex_grouping', False)
        self.with_bits_grouping = var.config_get('bits_grouping', True)

    def abs_qualname(self, node):
        qualname = node.qualname_from(self.qualstart)
        if self.qualstem is None:
            return qualname
        return self.qualstem + ('.' + qualname if qualname else '')

    def rel_qualname(self, node, is_root=True):
        start = len(self.root.path)
        if is_root:
            return node.qualname_from(start - 1)
        return '.' + node.qualname_from(start)

    def qualname(self, node, is_root=True):
        return self.abs_qualname(node) if self.abspath else self.rel_qualname(node, is_root)

    def size(self, value):
        value *= self.offset_scale
        return f'{value:,}'

    def offset(self, value):
        value *= self.offset_scale
        return f'0x{value:0{self.offset_nibbles}x}'

    def offset_range(self, start, end):
        return self.offset(start) + ' - ' + self.offset(end)

    def value_hex(self, value, region):
        if self.with_hex_grouping:
            # Groupings for 'x' and 'X' formatting are every four digits.
            # https://docs.python.org/3/library/string.html#format-specification-mini-language
            width = region.nibbles + (region.nibbles + 4 - 1) // 4 - 1
            grouping = '_'
        else:
            width = region.nibbles
            grouping = ''
        return '0x' + ('-' * width if value is None else f'{value:0{width}{grouping}x}')

    def value_bits(self, value, region):
        if self.with_bits_grouping:
            # Groupings for 'b' formatting are every four digits.
            # https://docs.python.org/3/library/string.html#format-specification-mini-language
            width = region.width + (region.width + 4 - 1) // 4 - 1
            grouping = '_'
        else:
            width = region.width
            grouping = ''
        return '0b' + ('-' * width if value is None else f'{value:0{width}{grouping}b}')

    def update_widths(self, widths, data):
        for key, value in data.items():
            if isinstance(value, str):
                wkey = f'w{key}'
                widths[wkey] = max(len(value), widths.get(wkey, 0))
        return data

    def __str__(self):
        root = self.root
        ctx = self.var._context
        chain = self.var._chain

        # Determine the set of nodes to be formatted.
        # - If the variable was created on a node group, iterate over all nodes in the router chain.
        # - If the variable was created on a singular node, use it.
        nodes = chain if chain.is_group else (root,)

        # Gather formatting data for all nodes in the variable's hierarchy.
        col_widths = {}
        row_data = []
        for node in nodes:
            # Format the node.
            col_data = ctx.new_variable(node, None, ...)._format_node(self, True)
            row_data.append(self.update_widths(col_widths, col_data))

            # Gather formatting data for each child node in the hierarchy.
            for child in node.descendants:
                col_data = ctx.new_variable(child, None, ...)._format_node(self, False)
                row_data.append(self.update_widths(col_widths, col_data))

        # Sort the row data by path instead of by node ordering the hierarchy.
        if self.path_sort:
            row_data = sorted(row_data, key=lambda d: d['path'])

        # Generate a string for each row.
        rows = self.format_rows(row_data, col_widths)

        # Setup heading separators to frame the row strings.
        return '\n'.join(rows)

#---------------------------------------------------------------------------------------------------
class TableFormatter(Formatter):
    COLUMN_HEADINGS = {
        'access': 'Access',
        'offset': 'Offset',
        'path': 'Path',
        'range': 'Range',
        'size': 'Size',
        'type': 'Type',
        'value_bits': 'Value',
        'value_hex': 'Value',
    }

    COLUMN_UNITS = {
        'value_hex': 'Hex',
        'value_bits': 'Bits',
    }

    COLUMN_FORMATS = {
        'access': '{access:{aaccess}{waccess}}',
        'offset': '{offset:{aoffset}{woffset}}',
        'path': '{path:{apath}{wpath}}',
        'range': '{range:{arange}{wrange}}',
        'size': '{size:{asize}{wsize}}',
        'type': '{type:{atype}{wtype}}',
        'value_bits': '{value_bits:{avalue_bits}{wvalue_bits}}',
        'value_hex': '{value_hex:{avalue_hex}{wvalue_hex}}',
    }

    COLUMN_LAYOUT_VERBOSE = 'rs//|,t/>/|,a/^/|,s/>/|,o/>/|,r/^/=,vh/</:,vb/</|,p/</,re//|'
    COLUMN_LAYOUT = 'rs//|,s/>/|,o/>/|,r/^/|,vh/</|,p/</,re//|'
    COLUMN_MAP = {
        'a': 'access',
        'o': 'offset',
        'p': 'path',
        'r': 'range',
        'rs': 'row_start',
        're': 'row_end',
        's': 'size',
        't': 'type',
        'vb': 'value_bits',
        'vh': 'value_hex',
    }

    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Determine the column layout to be displayed.
        col_layout = self.var.config_get('column_layout')
        if col_layout is None:
            col_layout = self.COLUMN_LAYOUT_VERBOSE if self.verbose else self.COLUMN_LAYOUT
        columns = col_layout.split(',')
        ncols = len(columns)

        col_align = {}
        row_fmt = ''
        csep = '/'
        for c, col in enumerate(columns):
            key, align, sep = col.split(csep)
            if key == 'rs':
                row_fmt += sep + ' '
                ncols -= 1
                continue
            if key == 're':
                row_fmt += ' ' + sep
                ncols -= 1
                continue

            name = self.COLUMN_MAP[key]
            col_align[f'a{name}'] = align
            row_fmt += self.COLUMN_FORMATS[name] + (f' {sep} ' if c < ncols - 1 else '')

        self.show_col_layout = self.var.config_get('show_column_layout', False)
        self.col_layout = col_layout
        self.col_align = col_align
        self.row_fmt = row_fmt

    def update_widths(self, widths, data):
        # Insert a column for each missing header to ensure a width is calculated for everything.
        data.update((h, '') for h in set(self.COLUMN_HEADINGS).difference(data))

        return super().update_widths(widths, data)

    def format_rows(self, row_data, col_widths):
        # Dump the column layout only.
        if self.show_col_layout:
            rows = [
                f'Default => column_layout={self.COLUMN_LAYOUT!r}',
                f'Verbose => column_layout={self.COLUMN_LAYOUT_VERBOSE!r}',
                '',
                'Mapping of column layout keys to header names:',
                'Key => Header',
            ]
            for key, name in sorted(self.COLUMN_MAP.items(), key=lambda pair: pair[0]):
                row = f'{key:^3} => {self.COLUMN_HEADINGS.get(name, name)}'
                units = self.COLUMN_UNITS.get(name, '')
                if units:
                    row += ' ' + units
                rows.append(row)
            return rows

        # Determine the units for the columns.
        offset_units = f'{self.offset_units}'
        units = dict(self.COLUMN_UNITS)
        units.update({
            'size': offset_units,
            'offset': offset_units,
        })

        # Insert the mapping between the stem and root names into the header.
        if self.qualstem is not None:
            units['path'] = f'{self.qualstem} => {self.qualroot}'

        # Wrap the unit names in parentheses.
        units = dict((k, f'({v})') for k, v in units.items())

        # Add rows for the header.
        row_data.insert(0, self.update_widths(col_widths, self.COLUMN_HEADINGS))
        row_data.insert(1, self.update_widths(col_widths, units))

        # Generate a string for each row.
        width = 0
        rows = []
        for col_data in row_data:
            row = self.row_fmt.format(**col_data, **col_widths, **self.col_align)
            width = max(width, len(row))
            rows.append(row)

        # Setup row separators to frame the headers.
        sep = '-' * width
        rows.insert(0, '=' * width)
        rows.insert(3, sep)
        rows.append(sep)

        return rows

#---------------------------------------------------------------------------------------------------
class PathFormatter(Formatter):
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Force qualnames to be absolute.
        self.abspath = True

    def format_rows(self, row_data, col_widths):
        return [col_data['path'] for col_data in row_data]

#---------------------------------------------------------------------------------------------------
class JsonFormatter(Formatter):
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Force qualnames to be absolute.
        self.abspath = True

    def format_rows(self, row_data, col_widths):
        import json
        return [json.dumps(row_data, indent=4)]

#---------------------------------------------------------------------------------------------------
FORMATTERS = {
    'json': JsonFormatter,
    'path': PathFormatter,
    'table': TableFormatter,
}

#---------------------------------------------------------------------------------------------------
class StructureFormatter:
    def _format_node(self, formatter, is_root=True):
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
            'path': formatter.qualname(self._node, is_root),
            'size': formatter.size(region.size),
            'offset': formatter.offset_range(start, end),
            'data': {
                'oid': region.oid,
                'ordinal': region.ordinal,
                'register': region.register,
                'data_width': region.data_width,
                'offset': region.offset.absolute,
                'size': region.size,
                'nibbles': region.nibbles,
                'octets': region.octets,
            },
        }

#---------------------------------------------------------------------------------------------------
class ArrayFormatter:
    def _format_node(self, formatter, is_root=True):
        region = self._node.region
        start = region.offset.absolute
        end = region.offset.absolute + region.size - 1
        qualname = formatter.qualname(self._node, is_root)
        subscripts = ''.join(f'[:{f}]' for f in self._node.indexer.fields)

        return {
            'type': 'Array',
            'path': f'{qualname}{subscripts}',
            'size': formatter.size(region.size),
            'offset': formatter.offset_range(start, end),
            'data': {
                'oid': region.oid,
                'ordinal': region.ordinal,
                'register': region.register,
                'data_width': region.data_width,
                'offset': region.offset.absolute,
                'size': region.size,
                'nibbles': region.nibbles,
                'octets': region.octets,
            },
        }

#---------------------------------------------------------------------------------------------------
class RegisterFormatter:
    def _format_node(self, formatter, is_root=True):
        region = self._node.region
        access = self._node.config.access
        value = int(self.proxy) if formatter.ignore_access or access.is_readable else None

        return {
            'type': 'Register',
            'access': self._node.config.access.name,
            'path': formatter.qualname(self._node, is_root),
            'size': formatter.size(region.size),
            'offset': formatter.offset(region.offset.absolute),
            'value_hex': formatter.value_hex(value, region),
            'data': {
                'oid': region.oid,
                'ordinal': region.ordinal,
                'register': region.register,
                'data_width': region.data_width,
                'access': self._node.config.access.value,
                'offset': region.offset.absolute,
                'size': region.size,
                'value': value,
                'width': region.width,
                'mask': region.mask,
                'shift': region.shift,
                'nibbles': region.nibbles,
                'octets': region.octets,
            },
        }

#---------------------------------------------------------------------------------------------------
class FieldFormatter:
    def _format_node(self, formatter, is_root=True):
        region = self._node.region
        access = self._node.config.access
        value = int(self.proxy) if formatter.ignore_access or access.is_readable else None

        range_ = f'{region.pos.absolute}'
        if region.width > 1:
            end = region.pos.absolute + region.width - 1
            range_ = f'{end}:' + range_

        return {
            'type': 'Field',
            'access': self._node.config.access.name,
            'path': formatter.qualname(self._node, is_root),
            'range': f'[{range_}]',
            'value_hex': formatter.value_hex(value, region),
            'value_bits': formatter.value_bits(value, region),
            'data': {
                'oid': region.oid,
                'ordinal': region.ordinal,
                'register': region.register,
                'data_width': region.data_width,
                'access': self._node.config.access.value,
                'offset': region.offset.absolute,
                'size': region.size,
                'value': value,
                'pos': region.pos.absolute,
                'width': region.width,
                'mask': region.mask,
                'shift': region.shift,
                'nibbles': region.nibbles,
                'octets': region.octets,
            },
        }

#---------------------------------------------------------------------------------------------------
class StructureVariable(Variable, StructureFormatter): ...
class ArrayVariable(Variable, ArrayFormatter): ...
class RegisterVariable(Variable, RegisterFormatter): ...
class FieldVariable(Variable, FieldFormatter): ...
