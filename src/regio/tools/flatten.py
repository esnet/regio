__all__ = (
    'main',
)

import click
from pathlib import Path
import sys

from . import parser

@click.command()
@click.option('-o', '--output-file',
              help="Output file for elaborated yaml file",
              default="-",
              show_default=True,
              type=click.File('w'))
@click.argument('yaml-file',
                type=click.File('r'))
def click_main(include_dirs, output_file, yaml_file):
    """Reads in a concise yaml regmap definition and flattens it into
    a single yaml file"""

    yaml = parser.load(yaml_file, include_dirs, {})
    parser.dump(yaml, output_file)

def main(inc_dir=None):
    inc_dir = str(Path.cwd()) if inc_dir is None else inc_dir
    click.option(
        'include_dirs',
        '-i', '--include-dir',
        help="Include directory for block definitions",
        default=[Path(inc_dir).absolute().joinpath('blocks')],
        multiple=True,
        show_default=True,
        type=click.Path(exists=True, file_okay=False, resolve_path=True))(click_main)
    click_main()

if __name__ == "__main__":
    main()
