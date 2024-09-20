__all__ = (
    'main',
)

import click
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

def decoders_from_regions(regions):
    return targets_from_list(regions, 'decoder', 'regions', True)

@click.command()
@click.option('-b', '--blocks',
              is_flag=True,
              help='Show all blocks referenced by all regions in the bar')
@click.option('-d', '--decoders',
              is_flag=True,
              help='Show all decoders referenced by all regions in the bar')
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(blocks, decoders, yaml_file):
    if not blocks and not decoders:
        blocks = True

    regmap = parser.load(yaml_file)

    blks = {}
    decs = {}
    top = regmap['toplevel']
    for bar in top['bars'].values():
        # Add all blocks and decoders referenced by all regions in the bar
        regions = bar['regions']
        # Add all blocks referenced by all regions in the bar
        blks.update(blocks_from_regions(regions))

        # Recursively add all decoders referenced by all regions in the bar
        decs.update(decoders_from_regions(regions))

    # Add all blocks referenced by the decoders
    for dec in decs.values():
        blks.update(blocks_from_regions(dec['regions']))

    if blocks:
        for name in sorted(blks):
            print(name)

    if decoders:
        for name in sorted(decs):
            print(name)

def main():
    click_main()

if __name__ == "__main__":
    main()
