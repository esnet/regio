
Install dependencies
====================
```
sudo apt install python3-yaml
pip install -r requirements.txt
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
./regio-elaborate -f block ./blocks.d/userbox.yaml
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
./regio-elaborate -f block ./blocks.d/userbox.yaml | \
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
      size: 131072
      blocks:
        - offset: 0x0000
          block: *alpha
          as: alpha_0
        - offset: 0x1000
          block: *alpha
          as: alpha_1
        - offset: 0x9000
          block: *bravo
    2:
      name: bar2
      desc: a one-line description of the bar
      size: 1048576
      blocks:
        - offset: 0x0000
          block: *charlie
```

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

