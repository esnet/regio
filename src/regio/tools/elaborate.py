__all__ = (
    'main',
)

import click
from pathlib import Path
import sys

from . import parser

#---------------------------------------------------------------------------------------------------
ACCESS_MODES = set(('ro', 'rw', 'wo', 'wr_evt', 'rd_evt'))

#---------------------------------------------------------------------------------------------------
def stderr(msg):
    sys.stderr.write(msg + '\n')

def log(obj, level, msg):
    try:
        metadata = obj.___metadata___
    except AttributeError:
        ...
    else:
        msg += f' [{metadata}]'
    stderr(f'{level}: {msg}')

def warning(obj, msg):
    log(obj, 'WARNING', msg)

def error(obj, msg):
    log(obj, 'ERROR', msg)

def fatal(obj, msg):
    error(obj, msg)
    sys.exit(1)

#---------------------------------------------------------------------------------------------------
def validate_attrs(obj, required, optional, deprecated, tag):
    if not isinstance(obj, dict):
        fatal(obj, f'A "{tag}" object must be specified as a mapping')

    # Track processed attributes to help in detecting errors in input YAML.
    attrs = set(obj.keys())

    # Require non-emptiness.
    if not attrs:
        fatal(obj, f'Missing attributes in "{tag}"')

    # Verify that all required attributes are present.
    for key, types in required:
        if key not in obj:
            fatal(obj, f'Missing required "{key}" attribute in "{tag}"')

        value = obj[key]
        if value is None:
            warning(obj, f'Required attribute "{key}" in "{tag}" has NULL value')
        elif not isinstance(value, types):
            fatal(obj, f'Invalid type for required "{key}" attribute in "{tag}". '
                  f'Expected {types}, got {type(value)}')
        attrs.remove(key)

    # Verify all optional attributes given.
    for key, types in optional:
        if key not in obj:
            continue

        value = obj[key]
        if value is None:
            warning(obj, f'Optional attribute "{key}" in "{tag}" has NULL value')
        elif not isinstance(value, types):
            fatal(obj, f'Invalid type for optional "{key}" attribute in "{tag}". '
                  f'Expected {types}, got {type(value)}')
        attrs.remove(key)

    # Warn about deprecated attributes.
    for key in deprecated:
        if key in obj:
            warning(obj, f'Attribute "{key}" in "{tag}" is deprecated and will be ignored')
            attrs.remove(key)

    # Check for unknown attributes.
    if attrs:
        unknown = ', '.join(sorted(attrs))
        fatal(obj, f'Found unknown attributes in "{tag}": {unknown}')

#---------------------------------------------------------------------------------------------------
def validate_field_defaults(defaults):
    tag = 'field-default'

    # Validate the attributes.
    OPTIONAL = (
        ('access', str),
        ('init', int),
        ('width', int),
    )
    validate_attrs(defaults, (), OPTIONAL, (), tag)

    # Verify that the given width is sensible.
    width = defaults.get('width')
    if width is not None and width < 1:
        fatal(defaults, 'The "width" of a "{tag}" must be at least 1 bit')

#---------------------------------------------------------------------------------------------------
def validate_field(fld):
    tag = 'field'
    if not isinstance(fld, dict):
        fatal(fld, 'A "{tag}" must be a mapping')

    # Validate as a meta-field.
    key = 'meta'
    if key in fld:
        OPTIONAL = (
            ('pad_until', int),
        )
        validate_attrs(fld[key], (), OPTIONAL, (), tag + '-meta')
        return

    # Validate the attributes.
    REQUIRED = (
        ('name', str),
    )
    OPTIONAL = (
        ('access', str),
        ('count', int),
        ('desc', str),
        ('enum_hex', dict),
        ('info', str),
        ('init', int),
        ('width', int),
    )
    validate_attrs(fld, REQUIRED, OPTIONAL, (), tag)

    # Verify the access mode if provided.
    access = fld.get('access')
    if access is not None and access not in ACCESS_MODES:
        choices = ', '.join(sorted(ACCESS_MODES))
        fatal(fld, f'Unknown value "{access}" for "access" in "{tag}". Choices are: {choices}')

    # Verify that the given width is sensible.
    width = fld.get('width')
    if width is not None and width < 1:
        fatal(fld, 'The "width" of a "{tag}" must be at least 1 bit')

    # Verify that the given count is sensible.
    count = fld.get('count')
    if count is not None and count < 1:
        fatal(fld, 'The "count" of a "{tag}" must be at least 1')

    # Verify the enumeration structure.
    enums = fld.get('enum_hex')
    if enums is not None:
        labels = set()
        values = set()
        for value, label in enums.items():
            # Validate the enumeration label.
            if not isinstance(label, str):
                fatal(enums, f'Enumeration label "{label}" for value "{value}" must be specified '
                      f'as a string, not a {type(label)}')

            # Check for duplicate enumeration labels.
            if label in labels:
                fatal(enums, f'Duplicate enumeration label "{label}"')
            labels.add(label)

            # Validate the enumeration value.
            if not isinstance(value, int):
                if isinstance(value, str):
                    warning(enums, f'Enumeration value "{value}" with label "{label}" should be '
                            'specified as an int.')
                    try:
                        ivalue = int(value, 16)
                    except ValueError:
                        fatal(enums, f'Enumeration value "{value}" with label "{label}" must be '
                              'specified as a base-16 int')
                else:
                    fatal(enums, f'Enumeration value "{value}" must be specified as an int, not a '
                          f'{type(value)}')

            # Check for duplicate enumeration labels. Note that this will only catch duplications
            # of values speficied as both int and str. Duplicate values of the same type will not
            # be noticed due to the nature of the mapping.
            svalue = str(value) # Converted to a string to match usage in templates/block_c.j2.
            if svalue in values:
                fatal(enums, f'Duplicate enumeration value "{value}"')
            values.add(svalue)

#---------------------------------------------------------------------------------------------------
def validate_register_defaults(defaults):
    tag = 'register-default'

    # Validate the attributes.
    OPTIONAL = (
        ('access', str),
        ('init', int),
        ('width', int),
    )
    validate_attrs(defaults, (), OPTIONAL, (), tag)

    # Verify that the given width is sensible.
    width = defaults.get('width')
    if width is not None and width < 1:
        fatal(defaults, 'The "width" of a "{tag}" must be at least 1 bit')

#---------------------------------------------------------------------------------------------------
def validate_register(reg):
    tag = 'register'
    if not isinstance(reg, dict):
        fatal(reg, 'A "{tag}" must be a mapping')

    # Validate as a meta-register.
    key = 'meta'
    if key in reg:
        OPTIONAL = (
            ('pad_until', int),
        )
        validate_attrs(reg[key], (), OPTIONAL, (), tag + '-meta')
        return

    # Validate the attributes.
    REQUIRED = (
        ('name', str),
    )
    OPTIONAL = (
        ('access', str),
        ('count', int),
        ('desc', str),
        ('fields', list),
        ('info', str),
        ('init', int),
        ('width', int),
    )
    validate_attrs(reg, REQUIRED, OPTIONAL, (), tag)

    # Verify the access mode if provided.
    access = reg.get('access')
    if access is not None and access not in ACCESS_MODES:
        choices = ', '.join(sorted(ACCESS_MODES))
        fatal(reg, f'Unknown value "{access}" for "access" in "{tag}". Choices are: {choices}')

    # Validate the list for specifying the registers.
    fields = reg.get('fields', ())
    for fld in fields:
        if not isinstance(fld, dict):
            error(reg, 'Register field must be specified as a mapping')
            fatal(fld, f'Register field of incorrect type {type(fld)}: {repr(fld)}')

    # Verify that the given width is sensible.
    width = reg.get('width')
    if width is not None and width < 1:
        fatal(reg, f'The "width" of a "{tag}" must be at least 1 bit')

    # Verify that the given count is sensible.
    count = reg.get('count')
    if count is not None and count < 1:
        fatal(reg, f'The "count" of a "{tag}" must be at least 1')

#---------------------------------------------------------------------------------------------------
def validate_block(blk):
    tag = 'block'
    if not isinstance(blk, dict):
        fatal(blk, 'A "{tag}" must be a mapping')

    # Validate the attributes.
    REQUIRED = (
        ('info', str),
        ('name', str),
        ('regs', list),
    )
    OPTIONAL = (
        ('desc', str),
    )
    validate_attrs(blk, REQUIRED, OPTIONAL, (), tag)

    # Validate the list for specifying the registers.
    for reg in blk['regs']:
        if not isinstance(reg, dict):
            error(blk, 'Register must be specified as a mapping')
            fatal(reg, f'Register of incorrect type {type(reg)}: {repr(reg)}')

#---------------------------------------------------------------------------------------------------
def validate_interface(intf):
    tag = 'interface'

    # Validate the object's attributes.
    REQUIRED = (
        ('address', int),
    )
    OPTIONAL = (
        ('block', dict),
        ('decoder', dict),
        ('name', str),
        ('size', int),
        ('suffix', str),
        ('width', int),
    )
    validate_attrs(intf, REQUIRED, OPTIONAL, (), tag)

    # Make sure that the interface has a target block or decoder, but not both.
    if 'block' in intf and 'decoder' in intf:
        fatal(intf, f'Must specify the target of an "{tag}" using either the "block" or "decoder" '
              'attribute, not both')
    if 'block' not in intf and 'decoder' not in intf:
        fatal(intf, f'Missing the target of an "{tag}". Specify using either the "block" or '
              '"decoder" attribute')

    # Make sure that the interface size is specified in one way.
    size = intf.get('size')
    width = intf.get('width')
    if size is not None and width is not None:
        fatal(intf, f'Must specify the size of an "{tag}" using either the "size" or "width" '
              'attribute, not both')

    # Verify that the given size is sensible.
    if size is not None and size < 1:
        fatal(intf, f'The "size" of an "{tag}" must be at least 1 byte')

    # Verify that the given width is sensible.
    if width is not None and width < 1:
        fatal(intf, f'The "width" of an "{tag}" must be at least 1 bit')

#---------------------------------------------------------------------------------------------------
def validate_decoder(dec):
    tag = 'decoder'

    # Validate the object's attributes.
    REQUIRED = (
        ('interfaces', list),
        ('name', str),
    )
    OPTIONAL = (
        ('blocks', dict),
        ('decoders', dict),
        ('info', str),
        ('visible', bool),
    )
    validate_attrs(dec, REQUIRED, OPTIONAL, (), tag)

    # Make sure that the decoder has blocks and/or decoders.
    if 'blocks' not in dec and 'decoders' not in dec:
        fatal(dec, f'Missing a "blocks" and/or "decoders" mapping needed by "{tag}"')

    # Validate the list for specifying the interfaces.
    for intf in dec['interfaces']:
        if not isinstance(intf, dict):
            error(dec, 'Decoder interfaces must be specified as a mapping')
            fatal(intf, f'Decoder interface of incorrect type {type(intf)}: {repr(intf)}')

#---------------------------------------------------------------------------------------------------
def validate_bar(bar):
    tag = 'bar'

    # Validate the object's attributes.
    REQUIRED = (
        ('decoder', dict),
        ('desc', str),
        ('name', str),
        ('size', int),
    )
    DEPRECATED = (
        'offset',
    )
    validate_attrs(bar, REQUIRED, (), DEPRECATED, tag)

#---------------------------------------------------------------------------------------------------
def validate_toplevel(top):
    tag = 'toplevel'

    # Validate the object's attributes.
    REQUIRED = (
        ('bars', dict),
        ('info', str),
        ('name', str),
        ('pci_device', int),
        ('pci_vendor', int),
    )
    validate_attrs(top, REQUIRED, (), (), tag)

    # Validate the structure for specifying the BARs.
    bars = top['bars']
    for bid, bar in bars.items():
        if not isinstance(bid, int):
            fatal(bars, f'BAR ID "{bid}" must be specified as an int, not a {type(bid)}')

        if not isinstance(bar, dict):
            error(bars, f'BAR {bid} must be specified as a mapping')
            fatal(bar, f'BAR {bid} of incorrect type {type(bar)}: {repr(bar)}')

#---------------------------------------------------------------------------------------------------
def compute_region_padding(regions, padding, min_offset=None, max_offset=None):
    merged_sorted = sorted(regions + padding, key=lambda r: r['offset'])
    if min_offset is None:
        if len(merged_sorted) > 0:
            # Just start wherever the first region starts
            first = merged_sorted[0]
            min_offset = first['offset']
        else:
            # No hints for where to start, just assume zero
            min_offset = 0

    if max_offset is None:
        if len(merged_sorted) > 0:
            # Just end wherever the last region ends
            last = merged_sorted[-1]
            max_offset = last['offset']+last['size']
        else:
            # No hints for where to end, just assume zero size
            max_offset = min_offset

    new_padding = []

    # Error path helper.
    def dump_regions():
        for region in merged_sorted:
            size = region['size']
            start = region['offset']
            end = start + size
            name = region.get('block', {}).get('name', '+++')
            stderr(f'\t0x{start:08x}-0x{end:08x} {name} ({size} (0x{size:08x}) bytes)')

    # Compute any required padding before the first region or between regions
    offset = min_offset
    for region in merged_sorted:
        if region['offset'] > offset:
            # Need padding before this region
            new_padding.append({
                'offset' : offset,
                'size'   : region['offset'] - offset,
            })
            offset = region['offset']
        elif region['offset'] < offset:
            # Overlapping regions
            start = region['offset']
            size = offset - start
            stderr(f'Overlapping regions at offset 0x{offset:08x}')
            stderr('Previous region overlaps this region (start offset '
                   f'0x{start:08x}) by {size} (0x{size:08x}) bytes')
            dump_regions()
            sys.exit(1)
        offset += region['size']

    # Compute any padding between the end of the last region and the max_offset
    if offset < max_offset:
        # Need padding to fill out to the max_offset
        new_padding.append({
            'offset' : offset,
            'size'   : max_offset - offset,
        })
        offset = max_offset
    elif offset > max_offset:
        # Contents exceed the size of the container
        size = offset - max_offset
        stderr(f'Regions exceed container by {size} (0x{size:08x}) bytes')
        stderr(f'Min: 0x{min_offset:08x}, Current: 0x{offset:08x}, Max: 0x{max_offset:08x}')
        dump_regions()
        sys.exit(1)

    return new_padding, max_offset - min_offset

#---------------------------------------------------------------------------------------------------
NAME_ESCAPE = str.maketrans('~!@#$%^&*()-+=;,./?',
                            '___________________')
def elaborate_name(obj):
    # Provide safe names
    safename = obj['name'].translate(NAME_ESCAPE)
    obj.update({
        'name':       safename,
        'name_lower': safename.lower(),
        'name_upper': safename.upper(),
    })

#---------------------------------------------------------------------------------------------------
def elaborate_field(fld, offset, defaults, parent):
    validate_field(fld)

    # Set up a new field based on current context
    fnew = defaults.copy()
    fnew.update({
        'offset': offset,
    })

    if 'meta' in fld:
        meta = fld['meta']
        if 'pad_until' in meta:
            if offset > meta['pad_until']:
                # Negative padding!
                fatal(fld, f'Negative padding requested at offset {offset}')
            elif offset == meta['pad_until']:
                # No padding required
                fatal(fld, f'Padding not required at offset {offset}')
            else:
                fnew.update({
                    'name':   f'anon{parent["synth_fld_cnt"]:03d}',
                    'access': 'none',
                    'width':  (meta['pad_until'] - offset)
                })
                parent['synth_fld_cnt'] += 1
    else:
        fnew.update(fld)

    # Compute the appropriate mask
    fnew.update({
        'mask':  ((1 << fnew['width']) - 1 << offset)
    })

    elaborate_name(fnew)

    return fnew

#---------------------------------------------------------------------------------------------------
def elaborate_register(reg, offset, defaults, parent):
    validate_register(reg)

    # Set up a new register based on current context
    rnew = defaults.copy()
    rnew.update({
        'offset': offset,
    })

    if 'meta' in reg:
        meta = reg['meta']
        if 'pad_until' in meta:
            if offset > meta['pad_until']:
                # Negative padding!
                fatal(reg, f'Negative padding requested at offset 0x{offset:08x}')
            elif offset == meta['pad_until']:
                # No padding required
                fatal(reg, f'Padding not required at offset 0x{offset:08x}')
            else:
                rnew.update({
                    'name':   f'anon{parent["synth_reg_cnt"]:03d}',
                    'access': 'none',
                    'width':  8,
                    'count':  (meta['pad_until'] - offset)
                })
                parent['synth_reg_cnt'] += 1
    else:
        # merge in the yaml register definition
        rnew.update(reg)

        # Elaborate the fields
        if 'fields' in rnew:
            fld_defaults = {
                'access': rnew['access'],
                'init': 0,
            }

            rnew['synth_fld_cnt'] = 0
            namespace = {}
            fld_offset = 0
            flds = []
            for fld in rnew['fields']:
                if 'default' in fld:
                    defaults = fld['default']
                    validate_field_defaults(defaults)
                    fld_defaults.update(defaults)
                    continue

                fnew = elaborate_field(fld, fld_offset, fld_defaults, rnew)
                flds.append(fnew)
                fld_offset += fnew['width']

                name = fnew['name']
                if name in namespace:
                    error(fld, f'Duplicate field name "{name}"')
                    error(namespace[name], f'Existing field with name "{name}"')
                    fatal(reg, f'Attempting to duplicate field name "{name}"')
                namespace[name] = fld

            rnew['fields'] = flds
            rnew['computed_width'] = fld_offset
            del rnew['synth_fld_cnt']

    elaborate_name(rnew)

    return rnew

#---------------------------------------------------------------------------------------------------
def elaborate_block(blk):
    validate_block(blk)
    elaborate_name(blk)

    # Set up some default defaults
    reg_defaults = {
        'count' : 1,
        'access' : 'ro',
        'init' : 0,
    }

    # Always ensure that every block has at least 1 register so we never generate empty struct
    # def'ns in C or C++. Make up a fake meta record that pads by a single byte which will auto-
    # generate an anon register in this block
    regs_in = blk['regs']
    if len(regs_in) == 0:
        regs_in.append({
            'meta': {
                'pad_until': 1,
            },
        })

    # Elaborate the regs
    blk['synth_reg_cnt'] = 0
    namespace = {}
    reg_offset = 0
    regs = []
    for reg in regs_in:
        if 'default' in reg:
            defaults = reg['default']
            validate_register_defaults(defaults)
            reg_defaults.update(defaults)
            continue

        rnew = elaborate_register(reg, reg_offset, reg_defaults, blk)
        regs.append(rnew)
        reg_offset += (rnew['width'] * rnew['count']) // 8

        name = rnew['name']
        if name in namespace:
            error(reg, f'Duplicate register name "{name}"')
            error(namespace[name], f'Existing register with name "{name}"')
            fatal(blk, f'Attempting to duplicate register name "{name}"')
        namespace[name] = reg

    blk['regs'] = regs
    blk['computed_size'] = reg_offset
    del blk['synth_reg_cnt']

#---------------------------------------------------------------------------------------------------
def elaborate_interface(intf, idx, parent):
    validate_interface(intf)

    if 'size' in intf:
        # size is explicitly specified and may not be a power of 2
        intf_max_size_bytes = intf['size']
    elif 'width' in intf:
        # size is explicitly specified as exactly a power of 2
        intf_max_size_bytes = 2**intf['width']
    else:
        # Size is dynamically calculated based on what this intf contains
        intf_max_size_bytes = None

    namespace = parent['namespace']
    def check_namespace(region):
        name = region['name']
        if name in namespace:
            error(intf, f'Duplicate region name "{name}"')
            error(namespace[name], f'Existing region with name "{name}"')
            fatal(parent, f'Attempting to duplicate region name "{name}"')
        namespace[name] = intf

    intf['regions'] = []
    intf['padding'] = []
    suffix = intf.get('suffix', '')
    if 'decoder' in intf:
        dec = intf['decoder']
        if dec.get('visible', False):
            new_region = {
                # use interface name, or fall back to decoder name
                # append any suffixes defined at this interface
                'name'    : intf.get('name', dec.get('name')) + suffix,
                'offset'  : intf['address'],
                'decoder' : dec,
                'size'    : dec['size'],
            }
            elaborate_name(new_region)
            check_namespace(new_region)
            intf['regions'].append(new_region)
        else:
            # bubble the regions upward, adding in this interface's offset
            for region in dec['regions']:
                new_region = region.copy()
                new_region['offset'] += intf['address']
                new_region['name'] += suffix
                elaborate_name(new_region)
                check_namespace(new_region)
                intf['regions'].append(new_region)

            # bubble the padding upward, adding in this interface's offset
            for pad in dec['padding']:
                new_pad = pad.copy()
                new_pad['offset'] += intf['address']
                intf['padding'].append(new_pad)
    elif 'block' in intf:
        blk = intf['block']
        new_region = {
            # use interface name, or fall back to block name
            # append any suffixes defined at this interface
            'name'   : intf.get('name', blk.get('name')) + suffix,
            'offset' : intf['address'],
            'block'  : blk,
            'size'   : blk['computed_size'],
        }
        elaborate_name(new_region)
        check_namespace(new_region)
        intf['regions'].append(new_region)

    # Make sure every interface has a name, autogenerate if necessary
    # Do this after evaluating the interfaces so regions don't pick up an autogen name
    # TODO: Figure out if this has side effects when the same decoder is elaborated more than once
    intf['name'] = intf.get('name', f'client_if_{idx:02d}')
    elaborate_name(intf)

    # Compute padding to fill out the interface
    if intf_max_size_bytes is not None:
        intf_max_address = intf['address'] + intf_max_size_bytes
    else:
        intf_max_address = None
    intf_padding, intf_size_bytes = compute_region_padding(
        intf['regions'], intf['padding'], intf['address'], intf_max_address)
    intf['padding'].extend(intf_padding)
    intf['size'] = intf_size_bytes

#---------------------------------------------------------------------------------------------------
def cmp_value(value_a, value_b):
    if isinstance(value_a, list):
        if not isinstance(value_b, list):
            return False
        if not cmp_list(value_a, value_b):
            return False
    elif isinstance(value_a, dict):
        if not isinstance(value_b, dict):
            return False
        if not cmp_dict(value_a, value_b):
            return False
    elif isinstance(value_a, (int, float, str, type(None))):
        if value_a != value_b:
            return False
    else:
        fatal(value_a, f'Unhandled comparison for type {type(value_a)}')
    return True

def cmp_list(list_a, list_b):
    if len(list_a) != len(list_b):
        return False

    for value_a, value_b in zip(list_a, list_b):
        if not cmp_value(value_a, value_b):
            return False
    return True

def cmp_dict(dict_a, dict_b):
    if not cmp_list(dict_a.keys(), dict_b.keys()):
        return False

    for key, value_a in dict_a.items():
        if not cmp_value(value_a, dict_b[key]):
            return False
    return True

def new_object_cache():
    return {
        'by_name': {},
        'by_id': set(),
    }

def is_cached_object(obj, cache):
    return id(obj) in cache['by_id']

def add_cached_object(obj, cache, parent, label):
    name = obj['name']
    instances = cache['by_name'].get(name)
    if instances is None:
        cache['by_name'][name] = [obj]
        cache['by_id'].add(id(obj))
        return

    if any(obj is inst for inst in instances):
        return

    inst = instances[0]
    if not cmp_dict(inst, obj):
        error(obj, f'Duplicate {label} "{name}"')
        error(inst, f'Existing {label} "{name}"')
        fatal(parent, f'Attempting to add duplicate {label} "{name}"')

    warning(obj, f'Duplicate {label} "{name}" with same content')
    warning(inst, f'Existing {label} "{name}" with same content')
    warning(parent, f'Adding duplicate {label} "{name}" with same content')

    cache['by_name'][name].append(obj)
    cache['by_id'].add(id(obj))

#---------------------------------------------------------------------------------------------------
def elaborate_decoder(dec, blocks, decoders):
    validate_decoder(dec)

    # Elaborate any referenced child blocks
    if 'blocks' in dec:
        for blk in dec['blocks'].values():
            if not is_cached_object(blk, blocks):
                elaborate_block(blk)
                add_cached_object(blk, blocks, dec, 'block')

    # Elaborate any referenced child decoders
    if 'decoders' in dec:
        for d in dec['decoders'].values():
            if not is_cached_object(d, decoders):
                elaborate_decoder(d, blocks, decoders)
                add_cached_object(d, decoders, dec, 'decoder')

    elaborate_name(dec)

    # Elaborate the region list from the interfaces defined in this decoder
    dec['regions'] = []
    dec['padding'] = []
    dec['namespace'] = {}
    if 'interfaces' in dec:
        for idx, intf in enumerate(dec['interfaces']):
            elaborate_interface(intf, idx, dec)

            dec['regions'].extend(intf['regions'])
            dec['padding'].extend(intf['padding'])
    del dec['namespace']

    # Compute padding required before and between interfaces
    decoder_padding, decoder_size = compute_region_padding(dec['regions'], dec['padding'], 0, None)
    dec['padding'].extend(decoder_padding)
    dec['size'] = decoder_size

#---------------------------------------------------------------------------------------------------
def elaborate_bar(bar, blocks, decoders):
    validate_bar(bar)
    elaborate_name(bar)

    # Elaborate the bar decoder
    dec = bar['decoder']
    elaborate_decoder(dec, blocks, decoders)

    # Promote all decoder regions up to the bar and pad it out to fill the bar
    bar['regions'] = dec['regions']
    bar_padding, bar_size = compute_region_padding(dec['regions'], dec['padding'], 0, bar['size'])
    bar['padding'] = dec['padding'] + bar_padding
    bar['size'] = bar_size

    # Fill in the size in pages
    PAGE_SIZE = 4096
    bar_size_pages = bar['size'] // PAGE_SIZE
    if bar['size'] % PAGE_SIZE > 0:
        bar_size_pages += 1
    bar['size_pages'] = bar_size_pages

#---------------------------------------------------------------------------------------------------
def elaborate_toplevel(top, blocks, decoders):
    validate_toplevel(top)
    elaborate_name(top)

    # Elaborate the bars
    for bar in top['bars'].values():
        elaborate_bar(bar, blocks, decoders)

#---------------------------------------------------------------------------------------------------
@click.command()
@click.option('-o', '--output-file',
              help='Output file for elaborated yaml file',
              default='-',
              show_default=True,
              type=click.File('w'))
@click.option('-f', '--file-type',
              help='Type of input yaml file',
              type=click.Choice(['top', 'block', 'decoder']),
              default='top',
              show_default=True)
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(include_dirs, output_file, file_type, yaml_file):
    '''
    Reads in a concise yaml regmap definition and fully elaborates it to produce a self-contained,
    verbose regmap file that can be used by code generators.
    '''
    regmap = parser.load(yaml_file, include_dirs, {})

    blocks = new_object_cache()
    decoders = new_object_cache()
    if file_type == 'top':
        toplevel = regmap['toplevel']
        elaborate_toplevel(toplevel, blocks, decoders)
    elif file_type == 'block':
        elaborate_block(regmap)
    elif file_type == 'decoder':
        elaborate_decoder(regmap, blocks, decoders)
    else:
        pass

    parser.dump(regmap, output_file)

#---------------------------------------------------------------------------------------------------
def main(inc_dir=None):
    inc_dir = str(Path.cwd()) if inc_dir is None else inc_dir
    click.option(
        'include_dirs',
        '-i', '--include-dir',
        help='Include directory for block definitions',
        default=[Path(inc_dir).absolute().joinpath('blocks')],
        multiple=True,
        show_default=True,
        type=click.Path(exists=True, file_okay=False, resolve_path=True))(click_main)
    click_main()

if __name__ == '__main__':
    main()
