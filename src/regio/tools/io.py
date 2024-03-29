__all__ = (
    'main',
)

import click
from pathlib import Path
import mmap
import sys
import struct
import os
import re

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

struct_width_map = {
     8 : "@B",
    16 : "@H",
    32 : "@I",
    64 : "@L",
}

# Note: It is essential to use a memoryview here rather than relying on
#       the struct module.  Using the struct module definitely results in double
#       reads to a register, possibly triggering side effects due to the
#       extra read.
# See: https://stackoverflow.com/a/53492789
def build_reg_cast(mem, offset, reg):
    addr   = offset + reg['offset']
    width  = reg['width']
    access = reg['access']
    count  = reg['count']

    # Create a sub-memoryview of just the bytes we're interested in
    reg_bytes = mem[addr:addr+((width>>3) * count)]
    # Cast the memview to the correct width
    reg_cast  = reg_bytes.cast(struct_width_map[width])

    return reg_cast

def update_field(reg_val, fld, fld_val):
    shift = fld['offset']
    mask  = (1 << fld['width']) - 1

    reg_val &= ~(mask << shift)
    reg_val |= ((fld_val & mask) << shift)

    return reg_val

SYSFS_BUS_PCI_DEVICES = "/sys/bus/pci/devices"

@click.command()
@click.option('-s', '--select',
              help="Select a specific PCIe device (domain:bus:device.function)",
              default="0000:d8:00.0",
              show_default=True)
@click.option('-b', '--bar',
              help="Select which PCIe bar to use for IO",
              default=2,
              show_default=True)
@click.option('-r', '--regmap',
              help="Path to fully elaborated regmap yaml file for this device",
              default='/usr/share/esnet-smartnic/esnet-smartnic-top-ir.yaml',
              show_default=True,
              type=click.File('r'))
@click.argument('register')
def click_main(select, bar, regmap, register):

    regmap = load(regmap, Loader=Loader)

    if not "toplevel" in regmap:
        print("ERROR: No toplevel defined in regmap.  Are you sure that's a regmap file?")
        sys.exit(1)

    toplevel = regmap['toplevel']
    if not "bars" in toplevel:
        print("ERROR: No bars defined in toplevel.  Are you sure that's a regmap file?")
        sys.exit(1)

    bars = toplevel['bars']
    if not bar in bars:
        print("ERROR: Bar {} is not defined in regmap (only {} are defined)".format(bar, ", ".join(["{:d}".format(b) for b in bars])))
        sys.exit(1)

    device_path = Path(SYSFS_BUS_PCI_DEVICES) / select
    if not device_path.exists():
        print("ERROR: Selected device does not exist.  Is the FPGA loaded and the PCIe bus rescanned?")
        sys.exit(1)

    resource_path = Path(SYSFS_BUS_PCI_DEVICES) / select / "resource{:d}".format(bar)
    if not resource_path.exists():
        print("ERROR: Selected bar does not exist for the selected device.  Is the FPGA loaded?")
        sys.exit(1)

    with resource_path.open('r+b') as f:
        m = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ | mmap.PROT_WRITE)
        mv = memoryview(m)

    from itertools import chain, repeat

    # Check if we have an assignment
    lhs, rhs, *_ = chain(register.split('='), repeat(None, 5))

    blk_name, reg_expr, fld_name, *_ = chain(lhs.split('.'), repeat(None, 5))

    if reg_expr is not None:
        # Check if we have an index or slice
        matches = re.match(r'^(?P<reg_name>[^\[\]]+)'
                           r'(\[(?P<index>[0-9]+)\]|'
                           r'\[((?P<slice_min>[0-9]+)?:)?(?P<slice_max>[0-9]+)?(:(?P<slice_inc>[0-9]+)?)?\])?$', reg_expr)
        if matches is None:
            print("ERROR: Unable to parse requested register expression '{}'".format(reg_expr))
            sys.exit(1)

        reg_name  = matches.group('reg_name')
        index     = matches.group('index')
        slice_min = matches.group('slice_min')
        slice_max = matches.group('slice_max')
        slice_inc = matches.group('slice_inc')

        # Convert any slice parameters to ints
        if index is not None:
            slice_min = int(index)
            slice_max = int(index) + 1
            slice_inc = 1
        else:
            if slice_min is not None:
                slice_min = int(slice_min)
            if slice_max is not None:
                slice_max = int(slice_max)
            if slice_inc is not None:
                slice_inc = int(slice_inc)
    else:
        reg_name  = None
        index     = None
        slice_min = None
        slice_max = None
        slice_inc = None

    if blk_name is None:
        print("ERROR: No block name specified in {}".format(lhs))
        sys.exit(1)

    # Build up the block name to block instance map
    region_map = {}
    for i, v in enumerate(bars[bar]['decoder']['regions']):
        # skip any padding blocks
        if 'anon' in v:
            continue

        if 'name' in v:
            region_map.update({ v['name'] : i })
        else:
            region_map.update({ v['block']['name'] : i })

    if not blk_name in region_map:
        print("ERROR: Bar {} does not contain a block called {}".format(bar, blk_name))
        sys.exit(1)

    region = bars[bar]['decoder']['regions'][region_map[blk_name]]
    blk = region['block']

    if reg_name is not None:
        # Build up the register name to register instance map
        reg_map = {v['name'] : i for (i, v) in enumerate(blk['regs'])}

        # Make sure we are referring to a valid register name in this block
        if reg_name not in reg_map:
            print("ERROR: Block {} does not contain a register called {}".format(blk_name, reg_name))
            sys.exit(1)

        reg = blk['regs'][reg_map[reg_name]]
    else:
        reg = None

    if fld_name is not None:
        # Build up the field name to field instance map for this register
        fld_map = {v['name'] : i for (i, v) in enumerate(reg['fields'])}

        # Make sure we are referring to a valid field name in this register
        if fld_name not in fld_map:
            print("ERROR: Register {} does not contain a field called {}".format(reg_name, fld_name))
            sys.exit(1)

        fld = reg['fields'][fld_map[fld_name]]
    else:
        fld = None

    # Validate additional constraints for assignments
    if rhs is not None:
        # Assignments must include at least a register name
        if reg is None:
            print("ERROR: Assignments must provide at least a register name")
            sys.exit(1)

        # Try to convert the rhs to an int directly
        if type(rhs) is str:
            try:
                rhs = int(rhs, 0)
            except ValueError:
                pass

        # Try to convert the rhs to an int via a field enum
        if type(rhs) is str:
            if fld is not None and 'enum_hex' in fld:
                # Build up the enum name to value instance map for this field
                enum_map = {v : k for k, v in fld['enum_hex'].items()}
                if rhs not in enum_map:
                    print("ERROR: Field {} does not contain an enum called {}".format(fld_name, rhs))
                    sys.exit(1)

                # Convert the enum to a value
                if type(enum_map[rhs]) is str:
                    rhs = int(enum_map[rhs], 16)
                else:
                    rhs = enum_map[rhs]

        if type(rhs) is not int:
            print("ERROR: Can't convert {} to a value".format(rhs))
            sys.exit(1)

        #
        # Ready to do a write operation
        #
        reg_cast = build_reg_cast(mv, region['offset'], reg)

        for reg_index in range(*slice(slice_min, slice_max, slice_inc).indices(len(reg_cast))):
            if fld is not None:
                # Need to do a read + modify before writing the register back
                v = update_field(reg_cast[reg_index], fld, rhs)
            else:
                # Use the rhs value directly since we're doing an entire register write
                v = rhs

            # perform the write to the register
            reg_cast[reg_index] = v

        sys.exit(0)

    #
    # We're just printing out blocks/registers/fields
    #

    def print_fields(reg, v, only_fld):
        width_map = {
             8 : "02x",
            16 : "04x",
            32 : "08x",
            64 : "016x",
        }

        width_map_no_zeros = {
             8 : " 2x",
            16 : " 4x",
            32 : " 8x",
            64 : " 16x",
        }

        offset = reg['computed_width']
        for fld in reversed(reg['fields']):
            if only_fld is not None and fld['name'] != only_fld['name']:
                continue
            start = offset - 1
            end = offset - fld['width']
            reg_fmt = width_map[reg['width']]
            fld_fmt = width_map_no_zeros[reg['width']]
            shift = fld['offset']
            mask  = (1 << fld['width']) - 1
            v_masked = v & (mask << shift)
            v_f = (v >> shift) & mask
            fld_name = fld['name']
            print(f'              {v_masked:{reg_fmt}}  [{start:-2d}:{end:-2d}]  {v_f:{fld_fmt}}  {fld_name}')
            offset -= fld['width']

    def print_reg(parent_base_addr, reg, reg_index, v, only_fld):
        reg_base_addr = parent_base_addr + reg['offset']

        if reg['count'] == 1:
            # not an array, use format without an index notation
            print("    {: 8X}: {:08x}  {}".format(reg_base_addr,
                                                  v,
                                                  reg['name']))
        else:
            # is an array, include the index notation
            print("    {: 8X}: {:08x}  {}[{:d}]".format(reg_base_addr+(reg_index*(reg['width']>>3)),
                                                        v,
                                                        reg['name'],
                                                        reg_index))
        if 'fields' in reg:
            print_fields(reg, v, only_fld)

    if reg_name is not None:
        reg_cast = build_reg_cast(mv, region['offset'], reg)

        for reg_index in range(*slice(slice_min, slice_max, slice_inc).indices(len(reg_cast))):
            print_reg(region['offset'], reg, reg_index, reg_cast[reg_index], fld)
    else:
        # Print out all of the defined registers in the block
        print("[{}]".format(blk_name))
        for reg in blk['regs']:
            offset = region['offset'] + reg['offset']
            access = reg['access']

            if reg['access'] == "none":
                continue
            elif reg['access'] == "wo":
                print("    {: 8x}: --------  {}".format(offset, reg['name']))
                continue
            else:
                reg_cast = build_reg_cast(mv, region['offset'], reg)

                for reg_index in range(*slice(slice_min, slice_max, slice_inc).indices(len(reg_cast))):
                    print_reg(region['offset'], reg, reg_index, reg_cast[reg_index], fld)

def main():
    click_main(auto_envvar_prefix='REGIO')

if __name__ == "__main__":
    main()
