__all__ = (
    'main',
)

import click
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

@click.command()
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(yaml_file):
    regmap = load(yaml_file, Loader=Loader)

    blks = {}
    top = regmap['toplevel']
    for _, bar in top['bars'].items():
        # Add all blocks referenced by all regions in the bar
        blks.update(blocks_from_regions(bar['regions']))

    for _, blk in blks.items():
        print(blk['name'])

def main():
    click_main()

if __name__ == "__main__":
    main()
