# Copyright Notice

ESnet SmartNIC Copyright (c) 2022, The Regents of the University of
California, through Lawrence Berkeley National Laboratory (subject to
receipt of any required approvals from the U.S. Dept. of Energy),
12574861 Canada Inc., Malleable Networks Inc., and Apical Networks, Inc.
All rights reserved.

If you have questions about your rights to use or distribute this software,
please contact Berkeley Lab's Intellectual Property Office at
IPO@lbl.gov.

NOTICE.  This Software was developed under funding from the U.S. Department
of Energy and the U.S. Government consequently retains certain rights.  As
such, the U.S. Government has been granted for itself and others acting on
its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the
Software to reproduce, distribute copies to the public, prepare derivative
works, and perform publicly and display publicly, and to permit others to do so.


# Support

The ESnet regio library is made available in the hope that it will
be useful to the FPGA design community. Users should note that it is
made available on an "as-is" basis, and should not expect any
technical support or other assistance with building or using this
software. For more information, please refer to the LICENSE.md file in
the source code repository.

The developers of the ESnet regio library can be reached by email at smartnic@es.net.


Install dependencies
====================
```
sudo apt install python3-yaml python3-jinja2 python3-click
pip3 install -r requirements.txt
```

Tool regio
==========
This tool is used to dump out raw register values and their fields on a running system.

**Note**: You must have a matching elaborated regmap for the running FPGA for this tool to work properly.  See `regio-elaborate` tool below for details of how you can generate this file.

Dump out all registers in a specific block
------------------------------------------
```
$ sudo ./regio syscfg
[syscfg]
           0: 20022300  build_status
           4: --------  system_reset
           8: 00000001  system_status
              00000001  [ 0: 0]         1  system_reset_done
           c: --------  shell_reset
          10: ffffffff  shell_status
              00000004  [ 2: 2]         1  cmac1_reset_done
              00000002  [ 1: 1]         1  cmac0_reset_done
              00000001  [ 0: 0]         1  qdma_reset_done
          14: --------  user_reset
          18: ffffffff  user_status
```

Dump out one specific register within a block
---------------------------------------------
```
$ sudo ./regio syscfg.shell_status
          10: ffffffff  syscfg.shell_status
              00000004  [ 2: 2]         1  cmac1_reset_done
              00000002  [ 1: 1]         1  cmac0_reset_done
              00000001  [ 0: 0]         1  qdma_reset_done
```

Writing to registers or fields within a register
------------------------------------------------
Field values can be set using enum names when defined for a given field
```
$ sudo ./regio ht_datapath.port_config.output_enable=PORT1
```

Register or field values can be written in binary (0b prefix), hex (0x prefix), octal (0o prefix) or decimal (no prefix)
```
$ sudo ./regio ht_datapath.port_config.output_enable=0b01
$ sudo ./regio ht_datapath.port_config=0xa
```

Advanced usage
--------------
The path to the regmap file may be specified as a command line parameter or as an environment variable.

Example using command line option
```
sudo ./regio --regmap /tmp/hightouch-top-ir.yaml syscfg
```

Example using an environment variable
```
export REGIO_REGMAP=/tmp/hightouch-top-ir.yaml
sudo ./regio syscfg
```

Tool regio-elaborate
====================

This tool is used to read a human-written, terse/brief yaml file that describes either a block of registers or an entire FPGA toplevel register map and to produce a self-contained, fully elaborated variant of the yaml file that can be used by code generators.

You can think of the elaborated version of the yaml file as an IR (Internal Representation) that includes every detail for every register explicitly written out.

Typical usage
-------------

Read an FPGA toplevel register map (`hightouch-top.yaml`) and produce an elaborated version (`hightouch-top-ir.yaml`).
```
./regio-elaborate -o /tmp/hightouch-top-ir.yaml toplevels/hightouch-top.yaml
```

This will:
* read the toplevel yaml file
* pull in any `!include`ed yaml files from the default location (see help output for default path)
* write out the fully elaborated yaml file

Advanced usage
--------------

Elaborate only a single block (rather than an entire toplevel definition) and dump the output to stdout
```
./regio-elaborate -f block ./blocks/userbox.yaml
```

Tool regio-generate
===================

This tool is used to generate code in various languages that can be used to interact with the registers defined in the input file.  The generators require a fully elaborated register map file as input.

All code generation is done by passing the full register map into various language-specific Jinja2 templates.

Typical usage
-------------

Read an elaborated toplevel yaml file and generate code for all available languages.
```
mkdir -p /tmp/some-output-dir
./regio-generate -o /tmp/some-output-dir /tmp/hightouch-top-ir.yaml
```

Advanced usage
--------------

Generate only sv code for a single block with elaborated yaml taken from stdin
```
mkdir -p /tmp/some-output-dir
./regio-elaborate -f block ./blocks/userbox.yaml | \
  ./regio-generate -f block -g sv -o /tmp/some-output-dir -
```

Regmap file format
==================

All input files are written in yaml.  External blocks can be pulled in by using a `!include` directive which is an extension to the yaml syntax.

There are two distinct types of input files which can be processed by the regio tools.
* Toplevel: Describes a complete FPGA PCIe register map along with all logic blocks contained in each PCIe BAR.
* Block: Describes a single logic block which is typically included in a toplevel

Toplevel
--------

A toplevel file must include a `blocks` section and a `toplevel` section.

``` yaml
blocks:
  alpha: &alpha
    name: alpha
    info: |
      This is a multi-line info string that provides documentation
      for the block.  Blocks can be inline like this one or can be
      included from external files.
    regs:
      - name: r1
        width: 64
        fields:
          - name: field1
            width: 64
  bravo: &bravo
    !include bravo.yaml
  charlie: &charlie
    !include charlie.yaml

toplevel:
  name: name_of_the_fpga
  info: |
    a multi-line description of the fpga
    that is described by this file
  pci_vendor: 0xabcd
  pci_device: 0x0123
  bars:
    0:
      name: bar0
      desc: a one-line description of the bar
      size: 0x00020000
	  decoder:
        name: bar0
        blocks:
          alpha: &alpha
            name: alpha
            info: |
              This is a multi-line info string that provides documentation
              for the block.  Blocks can be inline like this one or can be
              included from external files.
            regs:
              - name: r1
                width: 64
                fields:
                  - name: field1
                    width: 64
          bravo: &bravo
            !include bravo.yaml
        interfaces:
          - name: alpha_alice
            block: *alpha
            address: 0x000000
          - name: bravo_bob
            block: *bravo
            address: 0x001000
    2:
      name: bar2
      desc: a one-line description of the bar
      size: 0x00100000
	  decoder:
        name: bar2
        decoders:
          charlie_decoder: &charlie_decoder
            !include charlie_decoder.yaml
        interfaces:
          - decoder: *charlie_decoder
            address: 0x000000
            width: 14
            suffix: '0'
          - decoder: *charlie_decoder
            address: 0x008000
            width: 14
            suffix: '1'
```

Decoder level
-------------

```
name: stats

blocks:
  stats: &stats
    !include stats.yaml

decoders:
  foo: &foo_decoder
    !include foo_decoder.yaml

interfaces:
  - name: flow_pktbyte
    block: *stats
    address: 0x00000
    width: 12

  - name: flow_byte_histograms
    block: *stats
    address: 0x01000
    width: 12

  - decoder: *foo_decoder
    address: 0x10000
	size: 4000
```

A decoder consists of the following attributes
* name: the name of the decoder
* blocks: instances of blocks referenced in other sections
* decoders: instances of child decoders referenced in other sections
* interfaces: address ranges that map to other blocks or child decoders
  * name: (optional) name for this interface
    * used in generated sv decoders
	* used to override block names when a block is attached to the interface
	* if no name is specified here, one will be autogenerated where required
  * block/decoder: reference to the block or decoder attached to each interface
  * address: base address of each interface within the address space of this decoder
  * width: (optional) size of this interface's address space (2^width)
  * size: (optional) size of this interface's address space (can be non-power of 2)

Block level
-----------

A register consists of the following attributes
* name: the name of the register
* desc: a one-line description of the register
* width: the width in **bits** of this register
* offset: the offset in **bytes** of this register
  * automatically computed by `regio-elaborate` by packing each register next to the previous register in the list
  * must not be specified in the terse version of the regmap
* init: the initial value of the register (set by the FPGA on reset)
* access: the allowed access type for this register
  * ro: read-only
  * wo: write-only
  * rw: read-write
  * wr_evt: write-only
  * none: used to denote auto-generated, anonymous padding registers
* fields: a list of sub-fields within this register (see below for details)

A field within a register consists of the following attributes
* name: the name of the field
* desc: a one-line description of the field
* width: the width in **bits** of this field
* offset: the offset in **bits** of this field from the lsb of the register that contains it
* access: the allowed access type for this field
  * ro: read-only
  * wo: write-only
  * rw: read-write
  * none: used to denote auto-generated, anonymous padding fields
* enum_hex: a dictionary of hex values and their labels which will appear as an enum in each language

Pseudo entry types

In addition to the `register` and `field` definitions, there are 2 more pseudo entry types which can appear in the terse/brief regmap files.  These pseudo entries can be used to reduce repetition within the regmap files.

**Note** The pseudo entries are processed during elaboration and are removed from the final elaborated register map.

The `default` pseudo entry is used to set default attributes for all subsequent `register` or `field` entries (depending on context).  e.g. In the `register` context, the `default` pseudo entry can contain any of the attributes of a `register`.

The `meta` pseudo entry currently supports the following attributes which modify the metadata context during elaboration:
* pad_until: insert padding into the `register` or `field` to move the offset to the target value

