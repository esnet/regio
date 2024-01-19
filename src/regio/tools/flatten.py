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

@click.command()
@click.option('-o', '--output-file',
              help="Output file for elaborated yaml file",
              default="-",
              show_default=True,
              type=click.File('w'))
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(include_dir, output_file, yaml_file):
    """Reads in a concise yaml regmap definition and flattens it into
    a single yaml file"""

    if include_dir is not None:
        YamlIncludeConstructor.add_to_loader_class(loader_class=Loader, base_dir=include_dir)

    yaml = load(yaml_file, Loader=Loader)
    dump(yaml, output_file, Dumper=Dumper)

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
