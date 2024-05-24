__all__ = (
    'main',
)

import click
from pathlib import Path
import sys

from jinja2 import Template, Environment, FileSystemLoader

from . import parser

def targets_from_list(objects, target_key, recurse_key, recurse):
    targets = {}
    for obj in objects:
        tgt = obj.get(target_key)
        if tgt is not None:
            targets[tgt['name']] = tgt
            if recurse:
                targets.update(targets_from_list(tgt[recurse_key], target_key, recurse_key, True))
    return targets

def blocks_from_regions(regions):
    return targets_from_list(regions, 'block', 'regions', False)

def decoders_from_regions(regions, recurse=False):
    return targets_from_list(regions, 'decoder', 'regions', recurse)

def decoders_from_interfaces(interfaces):
    return targets_from_list(interfaces, 'decoder', 'interfaces', True)

@click.command()
@click.option('-t', '--template-dir',
              help="Path to the templates",
              default=Path(__file__).parent.absolute().joinpath('templates'),
              show_default=True,
              type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option('-o', '--output-dir',
              help="Path where output files will be written",
              required=True,
              type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option('-p', '--prefix',
              default='',
              help="Prefix added to all output file names")
@click.option('--recursive/--no-recursive',
              help="recursively evaluate all child blocks and decoders",
              default=False,
              show_default=True)
@click.option('-f', '--file-type',
              help="Type of input yaml file",
              type=click.Choice(['top', 'decoder', 'block']),
              default='top',
              show_default=True)
@click.option('-g', '--generator', "generators",
              help="Generator to use for producing the output",
              default=['sv', 'c'],
              show_default=True,
              multiple=True,
              type=click.Choice(['sv', 'svh', 'c', 'py']))
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(template_dir, output_dir, prefix, recursive, file_type, generators, yaml_file):
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    env.add_extension('jinja2.ext.loopcontrols')

    regmap = parser.load(yaml_file)

    top = None
    blks = {}
    all_decs = {}
    visible_decs = {}
    if file_type == "top":
        top = regmap['toplevel']
        top_blks = {}
        top_decs = {}
        for bar in top['bars'].values():
            # Add all blocks and decoders referenced by all regions in the bar
            regions = bar['regions']
            top_blks.update(blocks_from_regions(regions))
            top_decs.update(decoders_from_regions(regions))

            if recursive:
                dec = bar['decoder']
                all_decs[dec['name']] = dec

        if recursive:
            visible_decs.update(top_decs)
    elif file_type == "decoder":
        name = regmap['name']
        all_decs[name] = regmap
        visible_decs[name] = regmap # Force decoder to be visible to generate sources.
    elif file_type == "block":
        blks[regmap['name']] = regmap
    else:
        print("ERROR: No generator implemented for file type {}".format(file_type))
        sys.exit(1)

    if recursive:
        for dec in list(visible_decs.values()): # list is needed to prevent in-place update
            visible_decs.update(decoders_from_regions(dec['regions'], True))

        for dec in list(all_decs.values()): # list is needed to prevent in-place update
            all_decs.update(decoders_from_interfaces(dec['interfaces']))

        for dec in all_decs.values():
            blks.update(blocks_from_regions(dec['regions']))

    if 'sv' in generators:
        # for sv generators, produce only the outputs for the given file type, not for dependent file types

        # Produce all System Verilog output files for blocks
        for name, blk in blks.items():
            t = env.get_template('reg_pkg_sv.j2')
            outfilename = Path(output_dir) / (prefix + name + '_reg_pkg.sv')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

            t = env.get_template('reg_intf_sv.j2')
            outfilename = Path(output_dir) / (prefix + name + '_reg_intf.sv')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

            t = env.get_template('reg_blk_sv.j2')
            outfilename = Path(output_dir) / (prefix + name + '_reg_blk.sv')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

        # Produce all System Verilog output files for decoders
        for name, dec in all_decs.items():
            dec_blks = blocks_from_regions(dec['regions'])

            t = env.get_template('decoder_pkg_sv.j2')
            outfilename = Path(output_dir) / (prefix + name + '_decoder_pkg.sv')
            with outfilename.open(mode='w') as f:
                t.stream(dec = dec, blks = dec_blks).dump(f)

            t = env.get_template('decoder_sv.j2')
            outfilename = Path(output_dir) / (prefix + name + '_decoder.sv')
            with outfilename.open(mode='w') as f:
                t.stream(dec = dec, blks = dec_blks).dump(f)

    if 'svh' in generators:
        # for svh generators, produce only the outputs for the given file type, not for dependent file types

        # Produce all System Verilog header files for blocks.
        for name, blk in blks.items():
            t = env.get_template('reg_blk_agent_svh.j2')
            # Don't include prefix here.
            # These header files get bundled into verif package. The prefix is applied to the package file only.
            outfilename = Path(output_dir) / (name + '_reg_blk_agent.svh')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

    if 'c' in generators:
        # for c generators, produce all relevant dependent types

        # Produce all C language output files
        if top is not None:
            t = env.get_template('toplevel_c.j2')
            outfilename = Path(output_dir) / (prefix + top['name'] + '_toplevel.h')
            with outfilename.open(mode='w') as f:
                t.stream(top = top, blks = top_blks, decs = top_decs).dump(f)

        ctypes = {
             8 : "uint8_t ",
            16 : "uint16_t",
            32 : "uint32_t",
            64 : "uint64_t",
        }

        for name, blk in blks.items():
            t = env.get_template('block_c.j2')
            outfilename = Path(output_dir) / (prefix + name + '_block.h')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk, ctypes=ctypes).dump(f)

        for name, dec in visible_decs.items():
            dec_blks = blocks_from_regions(dec['regions'])
            sub_decs = decoders_from_regions(dec['regions'])

            t = env.get_template('decoder_c.j2')
            outfilename = Path(output_dir) / (prefix + name + '_decoder.h')
            with outfilename.open(mode='w') as f:
                t.stream(dec = dec, blks = dec_blks, decs = sub_decs, ctypes=ctypes).dump(f)

    if 'py' in generators:
        # for Python generators, produce all relevant dependent types
        output_path = Path(output_dir)

        # Produce all Python language output files
        if top is not None:
            # output_dir/
            # \--python/
            #    |-- pyproject.toml
            #    \-- regmap_<top.name>/
            #        |-- __init__.py
            #        |-- toplevel.py
            #        |-- regio.py
            #        |-- blocks/
            #        |   |-- __init__.py
            #        |   |-- block_0.py
            #        |   :
            #        |   \-- block_M.py
            #        \-- decoders/
            #            |-- __init__.py
            #            |-- decoder_0.py
            #            :
            #            \-- decoder_N.py
            output_path /= 'python'
            output_path.mkdir()

            t = env.get_template('pyproject_toml.j2')
            outfilename = output_path / 'pyproject.toml'
            with outfilename.open(mode='w') as f:
                t.stream(top = top).dump(f)

            output_path /= ('regmap_' + top['name'])
            output_path.mkdir()

            outfilename = output_path / '__init__.py'
            with outfilename.open(mode='w') as f:
                f.write('# NOTE: This file was autogenerated by regio.\n')

            t = env.get_template('toplevel_py.j2')
            outfilename = output_path / 'toplevel.py'
            with outfilename.open(mode='w') as f:
                t.stream(top = top, blks = top_blks, decs = top_decs).dump(f)

            t = env.get_template('regio_py.j2')
            outfilename = output_path / 'regio.py'
            with outfilename.open(mode='w') as f:
                t.stream(top = top).dump(f)

            sub_dirs = []
            if blks:
                sub_dirs.append('blocks')
            if visible_decs:
                sub_dirs.append('decoders')

            for sub_dir in sub_dirs:
                out_path = output_path / sub_dir
                out_path.mkdir()

                outfilename = out_path / '__init__.py'
                with outfilename.open(mode='w') as f:
                    f.write('# NOTE: This file was autogenerated by regio.\n')

        blk_tmpl = env.get_template('block_py.j2')
        for name, blk in blks.items():
            outfilename = output_path / ('' if top is None else 'blocks') / (name + '_block.py')
            with outfilename.open(mode='w') as f:
                blk_tmpl.stream(blk = blk).dump(f)

        dec_tmpl = env.get_template('decoder_py.j2')
        for name, dec in visible_decs.items():
            dec_blks = blocks_from_regions(dec['regions'])
            sub_decs = decoders_from_regions(dec['regions'])

            outfilename = output_path / ('' if top is None else 'decoders') / (name + '_decoder.py')
            with outfilename.open(mode='w') as f:
                dec_tmpl.stream(dec = dec, blks = dec_blks, decs = sub_decs).dump(f)

def main():
    click_main()

if __name__ == "__main__":
    main()
