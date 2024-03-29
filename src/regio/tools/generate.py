__all__ = (
    'main',
)

import click
from pathlib import Path
import sys

from jinja2 import Template, Environment, FileSystemLoader

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def blocks_from_regions(regions):
    blks = {}
    for region in regions:
        if 'block' in region:
            blk = region['block']
            blks.update({
                blk['name'] : blk
            })
    return blks

def get_decoder_tree(root):
    decoders = {}
    for intf in root['interfaces']:
        if 'decoder' in intf:
            dec = intf['decoder']
            decoders.update(get_decoder_tree(dec))
    decoders.update({
        root['name'] : root
    })
    return decoders

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

    regmap = load(yaml_file, Loader=Loader)

    if file_type == "top":
        top = regmap['toplevel']
        blks = {}
        decs = {}
        if recursive:
            for _, bar in top['bars'].items():
                # Add all blocks and decoders referenced by all regions in the bar
                blks.update(blocks_from_regions(bar['regions']))

                if 'decoder' in bar:
                    decs.update(get_decoder_tree(bar['decoder']))

    elif file_type == "decoder":
        top = None
        decs = {
            regmap['name'] : regmap
        }
        blks = {}
        if recursive:
            blks.update(blocks_from_regions(regmap['regions']))
            decs.update(get_decoder_tree(regmap))

    elif file_type == "block":
        top = None
        decs = {}
        blks = {
            regmap['name'] : regmap
        }
    else:
        print("ERROR: No generator implemented for file type {}".format(file_type))
        sys.exit(1)

    if 'sv' in generators:
        # for sv generators, produce only the outputs for the given file type, not for dependent file types

        # Produce all System Verilog output files for blocks
        for _, blk in blks.items():
            t = env.get_template('reg_pkg_sv.j2')
            outfilename = Path(output_dir) / (prefix + blk['name'] + '_reg_pkg.sv')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

            t = env.get_template('reg_intf_sv.j2')
            outfilename = Path(output_dir) / (prefix + blk['name'] + '_reg_intf.sv')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)
            
            t = env.get_template('reg_blk_sv.j2')
            outfilename = Path(output_dir) / (prefix + blk['name'] + '_reg_blk.sv')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

        # Produce all System Verilog output files for decoders
        for _, dec in decs.items():
            dec_blks = blocks_from_regions(dec['regions'])

            t = env.get_template('decoder_pkg_sv.j2')
            outfilename = Path(output_dir) / (prefix + dec['name'] + '_decoder_pkg.sv')
            with outfilename.open(mode='w') as f:
                t.stream(dec = dec, blks = dec_blks).dump(f)

            t = env.get_template('decoder_sv.j2')
            outfilename = Path(output_dir) / (prefix + dec['name'] + '_decoder.sv')
            with outfilename.open(mode='w') as f:
                t.stream(dec = dec, blks = dec_blks).dump(f)

    if 'svh' in generators:
        # for svh generators, produce only the outputs for the given file type, not for dependent file types

        # Produce all System Verilog header files for blocks.
        for _, blk in blks.items():
            t = env.get_template('reg_blk_agent_svh.j2')
            # Don't include prefix here.
            # These header files get bundled into verif package. The prefix is applied to the package file only.
            outfilename = Path(output_dir) / (blk['name'] + '_reg_blk_agent.svh')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

    if 'c' in generators:
        # for c generators, produce all relevant dependent types

        # Produce all C language output files
        if top is not None:
            t = env.get_template('toplevel_c.j2')
            outfilename = Path(output_dir) / (prefix + top['name'] + '_toplevel.h')
            with outfilename.open(mode='w') as f:
                t.stream(top = top, blks = blks).dump(f)

        ctypes = {
             8 : "uint8_t ",
            16 : "uint16_t",
            32 : "uint32_t",
            64 : "uint64_t",
        }

        for _, blk in blks.items():
            t = env.get_template('block_c.j2')
            outfilename = Path(output_dir) / (prefix + blk['name'] + '_block.h')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk, ctypes=ctypes).dump(f)

        for _,dec in decs.items():
            dec_blks = blocks_from_regions(dec['regions'])

            t = env.get_template('decoder_c.j2')
            outfilename = Path(output_dir) / (prefix + dec['name'] + '_decoder.h')
            with outfilename.open(mode='w') as f:
                t.stream(dec = dec, blks = dec_blks, ctypes=ctypes).dump(f)

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
            #        \-- blocks/
            #            |-- __init__.py
            #            |-- block_0.py
            #            :
            #            \-- block_N.py
            output_path /= 'python'
            output_path.mkdir()

            t = env.get_template('pyproject_toml.j2')
            outfilename = output_path / 'pyproject.toml'
            with outfilename.open(mode='w') as f:
                t.stream(top = top, blks = blks).dump(f)

            output_path /= ('regmap_' + top['name'])
            output_path.mkdir()

            outfilename = output_path / '__init__.py'
            with outfilename.open(mode='w') as f:
                f.write('# NOTE: This file was autogenerated by regio.\n')

            t = env.get_template('toplevel_py.j2')
            outfilename = output_path / 'toplevel.py'
            with outfilename.open(mode='w') as f:
                t.stream(top = top, blks = blks).dump(f)

            t = env.get_template('regio_py.j2')
            outfilename = output_path / 'regio.py'
            with outfilename.open(mode='w') as f:
                t.stream(top = top, blks = blks).dump(f)

            output_path /= 'blocks'
            output_path.mkdir()

            outfilename = output_path / '__init__.py'
            with outfilename.open(mode='w') as f:
                f.write('# NOTE: This file was autogenerated by regio.\n')

        for _, blk in blks.items():
            t = env.get_template('block_py.j2')
            outfilename = output_path / (blk['name'] + '_block.py')
            with outfilename.open(mode='w') as f:
                t.stream(blk = blk).dump(f)

def main():
    click_main()

if __name__ == "__main__":
    main()
