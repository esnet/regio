#---------------------------------------------------------------------------------------------------
__all__ = (
    'new_click_main',
    'new_proxy',
)

import click
import pathlib
import sys

from regio.regmap.io import *
from regio.regmap.proxy import ClickEnvironment, for_io_by_path

#---------------------------------------------------------------------------------------------------
THIS_FILE = pathlib.Path(sys.argv[0])

def test_path(pid, bid):
    return THIS_FILE.stem + f'.{pid}.bar{bid}.bin'

IO_TYPES = {
    'dict': lambda spec, pid, bid: DictIO(),
    'list': lambda spec, pid, bid: ListIOForSpec(spec),
    'mmap': lambda spec, pid, bid: FileMmapIOForSpec(spec, test_path(pid, bid)),
    'stream': lambda spec, pid, bid: FileStreamIOForSpec(spec, test_path(pid, bid)),
    'zero': lambda spec, pid, bid: ZeroIO(),
}

#---------------------------------------------------------------------------------------------------
PCI_DEVICES_DIR = pathlib.Path('/sys/bus/pci/devices')

def _hex_to_int(path):
    with path.open('r') as fo:
        return int(fo.read(), 16)

def pci_device_ids(vendor_id, device_id):
    return tuple(sorted(
        dev.name
        for dev in PCI_DEVICES_DIR.iterdir()
        if _hex_to_int(dev / 'vendor') == vendor_id and _hex_to_int(dev / 'device') == device_id
    ))

#---------------------------------------------------------------------------------------------------
def new_click_main(top, envvar_prefix=None):
    BAR_IDS = tuple(sorted(top.BAR_INFO))
    PCI_IDS = pci_device_ids(top.PCI_VENDOR, top.PCI_DEVICE)
    if not PCI_IDS:
        PCI_IDS = ('none',) # For testing.

    @click.group(
        invoke_without_command=True,
        context_settings={
            'help_option_names': ('--help', '-h'),
            'auto_envvar_prefix': envvar_prefix,
        },
        help=f'''
        Perform I/O operations on a PCI device using the {top.NAME} register mapping. Acceptable PCI
        devices must have vendor ID 0x{top.PCI_VENDOR:04x} and device ID 0x{top.PCI_DEVICE:04x}.
        ''',
    )
    @click.option(
        '-p', '--pci-id', 'pci_ids',
        help='Select PCIe device ID(s) to use for IO (domain:bus:device.function).',
        type=click.Choice(('all',) + PCI_IDS),
        default=(PCI_IDS[0],),
        show_default=True,
        show_envvar=True,
        multiple=True,
    )
    @click.option(
        '-b', '--bar-id', 'bar_ids',
        help='Select which PCIe BAR(s) to use map into memory for IO.',
        type=click.Choice(('all',) + BAR_IDS),
        default=('2',), # TODO: Shouldn't be hardcoded. Get from YAML?
        show_default=True,
        show_envvar=True,
        multiple=True,
    )
    @click.option(
        '-t', '--test-io',
        help='Run in test mode using an alternate IO type independent of hardware.',
        type=click.Choice(tuple(sorted(IO_TYPES))),
        show_envvar=True,
    )
    @ClickEnvironment.main_options
    @click.pass_context
    def click_main(ctx, pci_ids, bar_ids, test_io, **env_kargs):
        if 'all' in pci_ids:
            pci_ids = PCI_IDS

        if 'all' in bar_ids:
            bar_ids = BAR_IDS

        io_type = None if test_io is None else IO_TYPES[test_io]

        # Instantiate the selected top-level regmap specifications.
        specs = {}
        for bid in bar_ids:
            specs[bid] = top.BAR_INFO[bid]['spec_cls']()

        # Build a set of keyword arguments to configure the proxy.
        env = ctx.obj
        proxy_kargs = env.process_options(env_kargs)

        # Create the proxies for each selected PCI device and BAR ID combinations.
        for i, pid in enumerate(pci_ids):
            # Insert a name for the device into the execution environment.
            dev = env.new_variable(f'dev{i}')
            dev.pci_id = pid

            # Create the proxy on the BAR(s).
            for bid in bar_ids:
                io = None if io_type is None else io_type(specs[bid], pid, bid)
                proxy = top.BAR_INFO[bid]['new_proxy'](pid, specs[bid], io, **proxy_kargs)
                setattr(dev, f'bar{bid}', proxy)

        # Invoked for command line completion, so don't do anything more.
        if env.in_completion:
            return

        # A sub-command wasn't specified, so default to dumping all registers in the environment.
        if ctx.invoked_subcommand is None:
            ctx.invoke(click_main.get_command(ctx, 'dump'))

    env = ClickEnvironment(click_main)

    # Attach the environment to the opaque 'obj' attribute of the click context and return the
    # callable command object for implementing main.
    return click_main(obj=env)

#---------------------------------------------------------------------------------------------------
def new_proxy(pci_id, bar_id, spec_cls, spec=None, io=None, *pargs, **kargs):
    # Instantiate the regmap specification.
    if spec is None:
        spec = spec_cls()
    elif type(spec) is not spec_cls:
        raise TypeError(f'Invalid type for regmap specification {spec!r}. Expected {spec_cls!r}.')

    # Create the low-level IO accessor for the device.
    if io is None:
        io = DevMmapIOForSpec(spec, PCI_DEVICES_DIR / pci_id / f'resource{bar_id}')

    # Create the proxy.
    return for_io_by_path(spec, io, *pargs, **kargs)
