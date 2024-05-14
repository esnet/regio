__all__ = (
    'main',
)

import click
from pathlib import Path
import sys

from . import parser

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
            print(f'\t0x{start:08x}-0x{end:08x} {name} ({size} (0x{size:08x}) bytes)')

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
            print(f'Overlapping regions at offset 0x{offset:08x}')
            print('Previous region overlaps this region (start offset '
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
        print(f'Regions exceed container by {size} (0x{size:08x}) bytes')
        print(f'Min: 0x{min_offset:08x}, Current: 0x{offset:08x}, Max: 0x{max_offset:08x}')
        dump_regions()
        sys.exit(1)

    return new_padding, max_offset - min_offset

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

def elaborate_field(fld, offset, defaults, parent):
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
                print(f'Negative padding requested at offset {offset}')
                sys.exit(1)
            elif offset == meta['pad_until']:
                # No padding required
                print(f'Padding not required at offset {offset}')
                sys.exit(1)
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

def elaborate_register(reg, offset, defaults, parent):
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
                print(f'Negative padding requested at offset 0x{offset:08x}')
                sys.exit(1)
            elif offset == meta['pad_until']:
                # No padding required
                print(f'Padding not required at offset 0x{offset:08x}')
                sys.exit(1)
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
            fld_offset = 0
            flds = []
            for fld in rnew['fields']:
                if 'default' in fld:
                    fld_defaults.update(fld['default'])
                    continue

                fnew = elaborate_field(fld, fld_offset, fld_defaults, rnew)
                flds.append(fnew)
                fld_offset += fnew['width']

            rnew['fields'] = flds
            rnew['computed_width'] = fld_offset
            del rnew['synth_fld_cnt']

    elaborate_name(rnew)

    return rnew

def elaborate_block(blk):
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
    reg_offset = 0
    regs = []
    for reg in regs_in:
        if 'default' in reg:
            reg_defaults.update(reg['default'])
            continue

        rnew = elaborate_register(reg, reg_offset, reg_defaults, blk)
        regs.append(rnew)
        reg_offset += (rnew['width'] * rnew['count']) // 8

    blk['regs'] = regs
    blk['computed_size'] = reg_offset
    del blk['synth_reg_cnt']

def elaborate_interface(intf, idx, parent):
    if not 'address' in intf:
        print(f'Decoder {parent["name"]}: Missing "address" definition')
        sys.exit(1)

    if 'size' in intf:
        # size is explicitly specified and may not be a power of 2
        intf_max_size_bytes = intf['size']
    elif 'width' in intf:
        # size is explicitly specified as exactly a power of 2
        intf_max_size_bytes = 2**intf['width']
    else:
        # Size is dynamically calculated based on what this intf contains
        intf_max_size_bytes = None

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
            intf['regions'].append(new_region)
        else:
            # bubble the regions upward, adding in this interface's offset
            for region in dec['regions']:
                new_region = region.copy()
                new_region['offset'] += intf['address']
                new_region['name'] += suffix
                elaborate_name(new_region)
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

def elaborate_decoder(dec):
    # Elaborate any referenced child blocks
    if 'blocks' in dec:
        for _, blk in dec['blocks'].items():
            elaborate_block(blk)

    # Elaborate any referenced child decoders
    if 'decoders' in dec:
        for _, d in dec['decoders'].items():
            elaborate_decoder(d)

    elaborate_name(dec)

    # Elaborate the region list from the interfaces defined in this decoder
    dec['regions'] = []
    dec['padding'] = []
    if 'interfaces' in dec:
        for idx, intf in enumerate(dec['interfaces']):
            elaborate_interface(intf, idx, dec)

            dec['regions'].extend(intf['regions'])
            dec['padding'].extend(intf['padding'])

    # Compute padding required before and between interfaces
    decoder_padding, decoder_size = compute_region_padding(dec['regions'], dec['padding'], 0, None)
    dec['padding'].extend(decoder_padding)
    dec['size'] = decoder_size

def elaborate_bar(bar):
    elaborate_name(bar)

    # Elaborate the bar decoder
    dec = bar['decoder']
    elaborate_decoder(dec)

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

def elaborate_toplevel(top):
    elaborate_name(top)

    # Elaborate the bars
    for bar in top['bars'].values():
        elaborate_bar(bar)

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
def click_main(include_dir, output_file, file_type, yaml_file):
    '''
    Reads in a concise yaml regmap definition and fully elaborates it to produce a self-contained,
    verbose regmap file that can be used by code generators.
    '''
    regmap = parser.load(yaml_file, include_dir)

    if file_type == 'top':
        toplevel = regmap['toplevel']
        elaborate_toplevel(toplevel)
    elif file_type == 'block':
        elaborate_block(regmap)
    elif file_type == 'decoder':
        elaborate_decoder(regmap)
    else:
        pass

    parser.dump(regmap, output_file)

def main(inc_dir=None):
    inc_dir = str(Path.cwd()) if inc_dir is None else inc_dir
    click.option(
        '-i', '--include-dir',
        help='Include directory for block definitions',
        default=Path(inc_dir).absolute().joinpath('blocks'),
        show_default=True,
        type=click.Path(exists=True, file_okay=False, resolve_path=True))(click_main)
    click_main()

if __name__ == '__main__':
    main()
