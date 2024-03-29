__all__ = (
    'main',
)

import click
from pathlib import Path
import sys

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from yamlinclude import YamlIncludeConstructor

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
            print("Overlapping regions at offset", offset)
            print("  Previous region overlaps this region (start offset {:08x}) by {:08x} bytes".format(
                region['offset'],
                offset - region['offset'],))
            for r in merged_sorted:
                print("\t{:08x}-{:08x} {}".format(
                    r['offset'],
                    r['offset']+r['size'],
                    r.get('block',{}).get('name',"+++")))
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
        print("Regions exceed container by {:08x} bytes".format(offset - max_offset))
        print("Min: {:08x}  Current: {:08x}  Max: {:08x}".format(min_offset, offset, max_offset))
        for r in merged_sorted:
            print("\t{:08x}-{:08x} {}".format(
                r['offset'],
                r['offset']+r['size'],
                r.get('block',{}).get('name',"+++")))
        sys.exit(1)

    return new_padding, max_offset - min_offset

name_escape = str.maketrans("~!@#$%^&*()-+=;,./?",
                            "___________________")

def elaborate_fields(flds_in, defaults):
    # Set up some default defaults in addition to the ones inherited from the containing register
    defaults.update({
        'init': 0,
    })

    fld_offset = 0
    flds = []
    synth_fld_cnt = 0
    for fld in flds_in:
        if 'default' in fld:
            defaults.update(fld['default'])
            continue
        
        # Set up a new field based on current context
        fnew = {}
        fnew.update(defaults)
        fnew.update({
            'offset': fld_offset,
        })

        if 'meta' in fld:
            meta = fld['meta']
            if 'pad_until' in meta:
                if fld_offset > meta['pad_until']:
                    # Negative padding!
                    print("Negative padding requested at offset", fld_offset)
                    sys.exit(1)
                elif fld_offset == meta['pad_until']:
                    # No padding required
                    print("Padding not required at offset", fld_offset)
                    sys.exit(1)
                else:
                    fnew.update({
                        'name':   "anon{:03d}".format(synth_fld_cnt),
                        'access': 'none',
                        'width':  (meta['pad_until'] - fld_offset)
                    })
                    synth_fld_cnt += 1
        else:
            fnew.update(fld)

        # Provide safe names
        safename = fnew['name'].translate(name_escape)
        fnew.update({
            'name':       safename,
            'name_lower': safename.lower(),
            'name_upper': safename.upper(),
        })

        # Compute the appropriate mask
        fnew.update({
            'mask':  ((1 << fnew['width']) - 1 << fld_offset)
        })

        flds.append(fnew)
        fld_offset += fnew['width']

    return flds, fld_offset

def elaborate_regs(regs_in):
    # Set up some default defaults
    defaults = {
        'count' : 1,
        'access' : 'ro',
        'init' : 0,
    }

    if len(regs_in) == 0:
        # always ensure that every block has at least 1 register so we never generate empty struct def'ns in C or C++
        # make up a fake meta record that pads by a single byte which will auto-generate an anon register in this block
        regs_in.append({
            'meta': {
                'pad_until': 1,
            },
        })

    reg_offset = 0
    regs = []
    synth_reg_cnt = 0
    for reg in regs_in:
        if 'default' in reg:
            defaults.update(reg['default'])
            continue

        # Set up a new register based on current context
        rnew = {}
        rnew.update(defaults)
        rnew.update({
            'offset': reg_offset,
        })

        if 'meta' in reg:
            meta = reg['meta']
            if 'pad_until' in meta:
                if reg_offset > meta['pad_until']:
                    # Negative padding!
                    print("Negative padding requested at offset", reg_offset)
                    sys.exit(1)
                elif reg_offset == meta['pad_until']:
                    # No padding required
                    print("Padding not required at offset", reg_offset)
                    sys.exit(1)
                else:
                    rnew.update({
                        'name':   "anon{:03d}".format(synth_reg_cnt),
                        'access': 'none',
                        'width': 8,
                        'count':  (meta['pad_until'] - reg_offset)
                    })
                    synth_reg_cnt += 1
        else:
            # merge in the yaml register definition
            rnew.update(reg)
            if 'fields' in rnew:
                # Elaborate the fields
                field_defaults = {
                    'access': rnew['access']
                }
                rnew['fields'], rnew['computed_width'] = elaborate_fields(rnew['fields'], field_defaults)

        # Provide safe names
        safename = rnew['name'].translate(name_escape)
        rnew.update({
            'name':       safename.translate(name_escape),
            'name_lower': safename.lower(),
            'name_upper': safename.upper(),
        })

        regs.append(rnew)
        reg_offset += (rnew['width'] * rnew['count']) // 8

    return regs, reg_offset


def elaborate_block(blk):
    # Provide safe names
    safename = blk['name'].translate(name_escape)
    blk.update({
        'name':       safename,
        'name_lower': safename.lower(),
        'name_upper': safename.upper(),
    })

    # Elaborate the regs
    blk['regs'], blk['computed_size'] = elaborate_regs(blk['regs'])

def elaborate_decoder(dec):
    # Elaborate any referenced child blocks
    if 'blocks' in dec:
        for _, blk in dec['blocks'].items():
            elaborate_block(blk)

    # Elaborate any referenced child decoders
    if 'decoders' in dec:
        for _, d in dec['decoders'].items():
            elaborate_decoder(d)

    # Provide safe names
    safename = dec['name'].translate(name_escape)
    dec.update({
        'name':       safename,
        'name_lower': safename.lower(),
        'name_upper': safename.upper(),
    })

    # Elaborate the region list from the interfaces defined in this decoder
    dec['regions'] = []
    dec['padding'] = []
    if 'interfaces' in dec:
        for i, intf in enumerate(dec['interfaces']):
            if not 'address' in intf:
                print("Decoder {}: Missing 'address' definition".format(dec['name']))
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
            if 'decoder' in intf:
                # bubble the regions upward, adding in this interface's offset
                for region in intf['decoder']['regions']:
                    new_region = {
                        'name'       : region['name'],
                        'name_lower' : region['name_lower'],
                        'name_upper' : region['name_upper'],
                        'offset'     : intf['address'] + region['offset'],
                        'block'      : region['block'],
                        'size'       : region['size'],
                    }
                    if 'suffix' in intf:
                        name = new_region['name'] + intf['suffix']
                        safename = name.translate(name_escape)
                        new_region.update({
                            'name'       : safename,
                            'name_lower' : safename.lower(),
                            'name_upper' : safename.upper(),
                        })
                    intf['regions'].append(new_region)

                # bubble the padding upward, adding in this interface's offset
                for pad in intf['decoder']['padding']:
                    intf['padding'].append({
                        'offset' : intf['address'] + pad['offset'],
                        'size'   : pad['size'],
                    })

            elif 'block' in intf:
                blk = intf['block']
                new_region = {
                    'offset' : intf['address'],
                    'block'  : intf['block'],
                    'size'   : blk['computed_size'],
                }

                # use interface name, or fall back to block name
                name = intf.get('name', blk.get('name'))
                # append any suffixes defined at this interface
                name += intf.get('suffix', "")
                # generate a safename
                safename = name.translate(name_escape)
                new_region.update({
                    'name'       : safename,
                    'name_lower' : safename.lower(),
                    'name_upper' : safename.upper(),
                })
                intf['regions'].append(new_region)

            # Make sure every interface has a name, autgenerate if necessary
            # Do this after evaluating the interfaces so regions don't pick up an autogen name
            # TODO: Figure out if this has side effects when the same decoder is elaborated more than once
            safename = intf.get('name', "client_if_{:02d}".format(i)).translate(name_escape)
            intf.update({
                'name':       safename,
                'name_lower': safename.lower(),
                'name_upper': safename.upper(),
            })

            # Compute padding to fill out the interface
            if intf_max_size_bytes is not None:
                intf_max_address = intf['address'] + intf_max_size_bytes
            else:
                intf_max_address = None
            intf_padding, intf_size_bytes = compute_region_padding(intf['regions'], intf['padding'], intf['address'], intf_max_address)
            intf['padding'].extend(intf_padding)
            intf['size'] = intf_size_bytes

            dec['regions'].extend(intf['regions'])
            dec['padding'].extend(intf['padding'])

    # Compute padding required before and between interfaces
    decoder_padding, decoder_size = compute_region_padding(dec['regions'], dec['padding'], 0, None)
    dec['padding'].extend(decoder_padding)
    dec['size'] = decoder_size

    return

def elaborate_toplevel(top):
    PAGE_SIZE = 4096

    # Provide safe names
    safename = top['name'].translate(name_escape)
    top.update({
        'name':       safename,
        'name_lower': safename.lower(),
        'name_upper': safename.upper(),
    })

    # Elaborate the bars
    for barid, bar in top['bars'].items():
        # Provide safe names
        safename = bar['name'].translate(name_escape)
        bar.update({
            'name':       safename,
            'name_lower': safename.lower(),
            'name_upper': safename.upper(),
        })

        # Elaborate the top-level decoder
        dec = bar['decoder']
        elaborate_decoder(dec)

        # Promote all decoder regions up to the bar and pad it out to fill the bar
        bar['regions'] = dec['regions']
        bar_padding, bar_size = compute_region_padding(dec['regions'], dec['padding'], 0, bar['size'])
        bar['padding'] = dec['padding'] + bar_padding
        bar['size'] = bar_size

        # Fill in the size in pages
        bar_size_pages = bar['size'] // PAGE_SIZE
        if bar['size'] % PAGE_SIZE > 0:
            bar_size_pages += 1
        bar['size_pages'] = bar_size_pages


@click.command()
@click.option('-o', '--output-file',
              help="Output file for elaborated yaml file",
              default="-",
              show_default=True,
              type=click.File('w'))
@click.option('-f', '--file-type',
              help="Type of input yaml file",
              type=click.Choice(['top', 'block', 'decoder']),
              default='top',
              show_default=True)
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(include_dir, output_file, file_type, yaml_file):
    """Reads in a concise yaml regmap definition and fully
    elaborates it to produce a self-contained, verbose regmap 
    file that can be used by code generators"""
    
    if include_dir is not None:
        YamlIncludeConstructor.add_to_loader_class(loader_class=Loader, base_dir=include_dir)

    regmap = load(yaml_file, Loader=Loader)

    if file_type == "top":
        toplevel = regmap['toplevel']
        elaborate_toplevel(toplevel)
    elif file_type == "block":
        elaborate_block(regmap)
    elif file_type == "decoder":
        elaborate_decoder(regmap)
    else:
        pass

    dump(regmap, output_file, Dumper=Dumper)

def main(inc_dir=None):
    inc_dir = str(Path.cwd()) if inc_dir is None else inc_dir
    click.option(
        '-i', '--include-dir',
        help="Include directory for block definitions",
        default=Path(inc_dir).absolute().joinpath('blocks'),
        show_default=True,
        type=click.Path(exists=True, file_okay=False, resolve_path=True))(click_main)
    click_main()

if __name__ == "__main__":
    main()
