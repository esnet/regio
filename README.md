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


Setting up the Environment
==========================
The [Python poetry](https://python-poetry.org/) tool is used for development and packaging. It's inputs are specified via the `pyproject.toml` file.
* For development, poetry creates a Python virtual environment to manage dependencies, keeping them separate from the host's global Python installation.
* For distribution, poetry creates a standard Python wheel package which can be installed via pip. Aside from the core `regio` library, the following supporting scripts will also be installed:
  * `regio-elaborate`: Converts a YAML regmap specification into a single intermediate representation (IR) YAML file containing all details necessary for generating sources.
  * `regio-flatten`: Merges a subset of YAML regmap specification files into a single YAML file.
  * `regio-generate`: Translates an elaborated regmap YAML IR into source files for various languages.
  * `regio-info`: Displays the names of all blocks included in an elaborated regmap YAML IR.


Install dependencies
--------------------
```
pip3 install -r requirements.txt
```

Setup for development and testing
---------------------------------
```
poetry install --all-extras # Create a virtual environment and install the dependencies into it.
poetry shell                # Run within the virtual environment for testing.
```

Testing within the virtual environment
--------------------------------------
```
python3
>>> import regio
```

Build the distribution package
------------------------------
```
poetry build # The wheel package file is placed into the ./dist directory.
```

Install the distribution package
--------------------------------
```
pip3 install --find-links ./dist regio[shells]
```

Regmap Python Library
=====================
A Python library for an elaborated regmap can be produced with the `regio-generate` tool. The Python library is named `regmap_<top-name>`, where `top-name` is taken from the `name` attribute of the regmap's `toplevel` object.

Generate the Python library from an elaborated regmap
-----------------------------------------------------
```
mkdir build
regio-generate --output-dir=build --file-type=top --generator=py --recursive esnet-smartnic-top-ir.yaml
```

Install the Python library into the virtual environment
-------------------------------------------------------
```
pushd build/python
poetry install
popd
```

Testing the Python library within the virtual environment
---------------------------------------------------------
```
python3
>>> import regmap_esnet_smartnic
```

Build the Python library distribution package
---------------------------------------------
```
pushd build/python
poetry build
popd
```

Install the Python library distribution package
-----------------------------------------------
```
pip3 install --find-links ./build/python/dist regmap_esnet_smartnic
```

Tool regio
==========
This tool is used to access register values and their fields on a running system. The tool is generated as part of the regmap Python library and is exported as a script named `regio-<top-dashed-name>`, where `top-dashed-name` is taken from the `name` attribute of the regmap's `toplevel` object with all underscores replaced by dashes.

Enable regio tool bash completions
----------------------------------
The regio tool supports bash completions for decoder, block, register and field names. It can be enable is the current shell as follows:
```
eval "$(regio-esnet-smartnic -t zero -p none completions bash)"
```

Dump out all registers in a specific block
------------------------------------------
```
regio-esnet-smartnic dump dev0.bar2.syscfg # Alternatively: regio-esnet-smartnic eval 'print(dev0.bar2.syscfg())'
===================================================================================
|    Size |      Offset | Range | Value      | Path                               |
| (Bytes) |     (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2) |
-----------------------------------------------------------------------------------
|      44 | 0x00 - 0x28 |       |            | syscfg                             |
|       4 |        0x00 |       | 0x05170816 | .build_status                      |
|       4 |        0x04 |       | 0x-------- | .system_reset                      |
|         |             |  [0]  | 0x-        | .system_reset.system_reset         |
|       4 |        0x08 |       | 0x00000001 | .system_status                     |
|         |             |  [0]  | 0x1        | .system_status.system_reset_done   |
|       4 |        0x0c |       | 0x-------- | .shell_reset                       |
|         |             |  [2]  | 0x-        | .shell_reset.cmac1_reset           |
|         |             |  [1]  | 0x-        | .shell_reset.cmac0_reset           |
|         |             |  [0]  | 0x-        | .shell_reset.qdma_reset            |
|       4 |        0x10 |       | 0xffffffff | .shell_status                      |
|         |             |  [2]  | 0x1        | .shell_status.cmac1_reset_done     |
|         |             |  [1]  | 0x1        | .shell_status.cmac0_reset_done     |
|         |             |  [0]  | 0x1        | .shell_status.qdma_reset_done      |
|       4 |        0x14 |       | 0x-------- | .user_reset                        |
|       4 |        0x18 |       | 0xffffffff | .user_status                       |
|       4 |        0x1c |       | 0x0000c9f2 | .usr_access                        |
|      12 | 0x20 - 0x28 |       |            | .dna[:3]                           |
|       4 | 0x20 - 0x20 |       |            | .dna[0]                            |
|       4 |        0x20 |       | 0x04202205 | .dna[0]._r                         |
|       4 | 0x24 - 0x24 |       |            | .dna[1]                            |
|       4 |        0x24 |       | 0x013ae323 | .dna[1]._r                         |
|       4 | 0x28 - 0x28 |       |            | .dna[2]                            |
|       4 |        0x28 |       | 0x40020000 | .dna[2]._r                         |
-----------------------------------------------------------------------------------
```

Dump out one specific register within a block
---------------------------------------------
```
regio-esnet-smartnic dump dev0.bar2.syscfg.shell_status # Alternatively: regio-esnet-smartnic eval 'print(dev0.bar2.syscfg.shell_status())'
===============================================================================
|    Size |  Offset | Range | Value      | Path                               |
| (Bytes) | (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2) |
-------------------------------------------------------------------------------
|       4 |    0x10 |       | 0xffffffff | shell_status                       |
|         |         |  [2]  | 0x1        | .cmac1_reset_done                  |
|         |         |  [1]  | 0x1        | .cmac0_reset_done                  |
|         |         |  [0]  | 0x1        | .qdma_reset_done                   |
-------------------------------------------------------------------------------

# Dump as an integer (without tabular field information).
regio-esnet-smartnic eval 'print(dev0.bar2.syscfg.shell_status)'
0xffffffff
```

Writing to registers or fields within a register
------------------------------------------------
```
# Dump the state before making changes.
regio-esnet-smartnic dump dev0.bar2.endian_check
=================================================================================================
|    Size |              Offset | Range | Value      | Path                                     |
| (Bytes) |             (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2)       |
-------------------------------------------------------------------------------------------------
|      40 | 0x200400 - 0x200424 |       |            | endian_check                             |
|       4 |            0x200400 |       | 0x00000000 | .scratchpad_packed                       |
|       4 |            0x200404 |       | 0x00000000 | .scratchpad_packed_monitor_byte_0        |
|         |                     | [7:0] | 0x00       | .scratchpad_packed_monitor_byte_0.byte_0 |
|       4 |            0x200408 |       | 0x00000000 | .scratchpad_packed_monitor_byte_1        |
|         |                     | [7:0] | 0x00       | .scratchpad_packed_monitor_byte_1.byte_1 |
|       4 |            0x20040c |       | 0x00000000 | .scratchpad_packed_monitor_byte_2        |
|         |                     | [7:0] | 0x00       | .scratchpad_packed_monitor_byte_2.byte_2 |
|       4 |            0x200410 |       | 0x00000000 | .scratchpad_packed_monitor_byte_3        |
|         |                     | [7:0] | 0x00       | .scratchpad_packed_monitor_byte_3.byte_2 |
|       4 |            0x200414 |       | 0x00000000 | .scratchpad_unpacked_byte_0              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_0.byte_0       |
|       4 |            0x200418 |       | 0x00000000 | .scratchpad_unpacked_byte_1              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_1.byte_1       |
|       4 |            0x20041c |       | 0x00000000 | .scratchpad_unpacked_byte_2              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_2.byte_2       |
|       4 |            0x200420 |       | 0x00000000 | .scratchpad_unpacked_byte_3              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_3.byte_3       |
|       4 |            0x200424 |       | 0x00000000 | .scratchpad_unpacked_monitor             |
-------------------------------------------------------------------------------------------------

# Change a register's value.
regio-esnet-smartnic eval dev0.bar2.endian_check.scratchpad_packed=0x12345678

# Dump the state after making changes.
regio-esnet-smartnic dump dev0.bar2.endian_check
=================================================================================================
|    Size |              Offset | Range | Value      | Path                                     |
| (Bytes) |             (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2)       |
-------------------------------------------------------------------------------------------------
|      40 | 0x200400 - 0x200424 |       |            | endian_check                             |
|       4 |            0x200400 |       | 0x12345678 | .scratchpad_packed                       |
|       4 |            0x200404 |       | 0x00000078 | .scratchpad_packed_monitor_byte_0        |
|         |                     | [7:0] | 0x78       | .scratchpad_packed_monitor_byte_0.byte_0 |
|       4 |            0x200408 |       | 0x00000056 | .scratchpad_packed_monitor_byte_1        |
|         |                     | [7:0] | 0x56       | .scratchpad_packed_monitor_byte_1.byte_1 |
|       4 |            0x20040c |       | 0x00000034 | .scratchpad_packed_monitor_byte_2        |
|         |                     | [7:0] | 0x34       | .scratchpad_packed_monitor_byte_2.byte_2 |
|       4 |            0x200410 |       | 0x00000012 | .scratchpad_packed_monitor_byte_3        |
|         |                     | [7:0] | 0x12       | .scratchpad_packed_monitor_byte_3.byte_2 |
|       4 |            0x200414 |       | 0x00000000 | .scratchpad_unpacked_byte_0              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_0.byte_0       |
|       4 |            0x200418 |       | 0x00000000 | .scratchpad_unpacked_byte_1              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_1.byte_1       |
|       4 |            0x20041c |       | 0x00000000 | .scratchpad_unpacked_byte_2              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_2.byte_2       |
|       4 |            0x200420 |       | 0x00000000 | .scratchpad_unpacked_byte_3              |
|         |                     | [7:0] | 0x00       | .scratchpad_unpacked_byte_3.byte_3       |
|       4 |            0x200424 |       | 0x00000000 | .scratchpad_unpacked_monitor             |
-------------------------------------------------------------------------------------------------

# Change a register field's value.
regio-esnet-smartnic eval dev0.bar2.endian_check.scratchpad_unpacked_byte_0.byte_0=0xab

# Dump the state after making changes.
regio-esnet-smartnic dump dev0.bar2.endian_check.scratchpad_unpacked_byte_0
================================================================================
|    Size |   Offset | Range | Value      | Path                               |
| (Bytes) |  (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2) |
--------------------------------------------------------------------------------
|       4 | 0x200414 |       | 0x000000ab | scratchpad_unpacked_byte_0         |
|         |          | [7:0] | 0xab       | .byte_0                            |
--------------------------------------------------------------------------------
```

Register or field values can be written in binary (0b prefix), hex (0x prefix), octal (0o prefix) or decimal (no prefix).
```
regio-esnet-smartnic eval dev0.bar2.endian_check.scratchpad_unpacked_byte_1.byte_1=0b1100_1101
regio-esnet-smartnic dump dev0.bar2.endian_check.scratchpad_unpacked_byte_1
================================================================================
|    Size |   Offset | Range | Value      | Path                               |
| (Bytes) |  (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2) |
--------------------------------------------------------------------------------
|       4 | 0x200418 |       | 0x000000cd | scratchpad_unpacked_byte_1         |
|         |          | [7:0] | 0xcd       | .byte_1                            |
--------------------------------------------------------------------------------

regio-esnet-smartnic eval dev0.bar2.endian_check.scratchpad_unpacked_byte_2.byte_2=0o357
regio-esnet-smartnic dump dev0.bar2.endian_check.scratchpad_unpacked_byte_2
================================================================================
|    Size |   Offset | Range | Value      | Path                               |
| (Bytes) |  (Bytes) |       | (Hex)      | (dev0.bar2 => esnet_smartnic_bar2) |
--------------------------------------------------------------------------------
|       4 | 0x20041c |       | 0x000000ef | scratchpad_unpacked_byte_2         |
|         |          | [7:0] | 0xef       | .byte_2                            |
--------------------------------------------------------------------------------
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

The following are the distinct types of input files which can be processed by the regio tools.
* Toplevel: Describes a complete FPGA PCIe register map along with all logic blocks contained in each PCIe BAR.
* Block: Describes a single logic block. Is typically included in a toplevel or a decoder.
* Decoder: Describes a grouping of blocks and sub-decoders. Is included in a toplevel or parent decoder.

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
* visible: (optional) boolean flag to control the decoder's visibility in the register map hierarchy
  * when "false" or missing, the decoder interfaces will replace the decoder in the register map hierarchy
    * all interfaces under a decoder are effectively "pulled-up" or "flattened" to the decoder's level in the hierarchy, making the decoder transparent
  * when "true", the decoder will remain in the register map hierarchy
    * all interfaces under a decoder will remain as is in the register map hierarchy, making the decoder non-transparent
  * primarily used by `regio-generate` when defining the register map overlay structures
* data_width: specifies the bit width of a data word (defaults to the width of the interfaces, which must all be the same)
* blocks: instances of blocks referenced in other sections
* decoders: instances of child decoders referenced in other sections
* protocol: specifies that the decoder implements an indirect memory controller and provides the Python source for accessing it with the `regio` tool (refer to the Protocols section for details)
* interfaces: address ranges that map to other blocks or child decoders
  * name: (optional) name for this interface
    * used in generated sv decoders
	* used to override block names when a block is attached to the interface
	* if no name is specified here, one will be autogenerated where required
  * block/decoder: reference to the block or decoder attached to each interface
  * address: base address of each interface within the address space of this decoder
  * width: (optional) size of this interface's address space (2^width)
  * size: (optional) size of this interface's address space (can be non-power of 2)
  * view: defines the indirect memory accessible from the interface's target block or decoder (refer to the Protocols section for details)

Block level
-----------
A block consists of the following attributes
* name: the name of the block
* info: documentation string to describe the block's function
* data_width: specifies the bit width of a data word (defaults to 32 bits)
* protocol: specifies that the block implements an indirect memory controller and provides the Python source for accessing it with the `regio` tool (refer to the Protocols section for details)
* regs: list of registers implemented by the block

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
* enum_hex: a dictionary of hex values (given as strings) and their labels which will appear as an enum in each language
  * Deprecated. Please use "enum" instead.
  * Will be removed in a future release.
* enum: a dictionary of integer values and their labels which will appear as an enum in each language

Pseudo entry types

In addition to the `register` and `field` definitions, there are 2 more pseudo entry types which can appear in the terse/brief regmap files.  These pseudo entries can be used to reduce repetition within the regmap files.

**Note** The pseudo entries are processed during elaboration and are removed from the final elaborated register map.

The `default` pseudo entry is used to set default attributes for all subsequent `register` or `field` entries (depending on context).  e.g. In the `register` context, the `default` pseudo entry can contain any of the attributes of a `register`.

The `meta` pseudo entry currently supports the following attributes which modify the metadata context during elaboration:
* pad_until: insert padding into the `register` or `field` to move the offset to the target value

Protocols
---------
Protocols allow accessing memories that are not directly mapped into the top-level address space. Such a memory is part of a separate address space and is accessed indirectly via a controller whose role is to bridge two distinct address spaces. Using a protocol requires defining a view on the decoder interface through which the controller registers are available. The views are rendered into the Python library produced by the `regio-generate` tool as virtual nodes that appear similar to a block or nested decoder. In conjunction with a per-view instance of a protocol, the `regio` tool grants access to the memories behind the views transparently, using the same syntax as directly accessible registers.

The following YAML snippets demonstrate how to declare a protocol within the block for a controller and how to declare a view that references it within a decoder interface:
```
# Snippet taken from test/protocol/spec/protocol_single_controller.yaml
protocol:
  name: slots
  source: !include protocol_slots.py

# Snippet taken from test/protocol/spec/protocol_top.yaml
decoder:
  blocks:
    single_controller: &single_controller
      !include protocol_single_controller.yaml
    single_view: &single_view
      !include protocol_single_view.yaml
  interfaces:
    - name: single_controller
      block: *single_controller
      address: 0x00000
      width: 16
      view:
        name: single_view
        block: *single_view
```

Refer to the `test/protocol/spec` directory for the complete regmap specification.

A protocol consists of the following attributes:
* name: The name of the protocol. The name and source must form a globally unique pair to ensure that the `regio-generate` tool is able to correctly associate the source with the views that use it in the generated regmap library.
* source: The Python code implementing the protocol. The methods of a protocol class will be invoked automatically by the `regio` tool when a Python library proxy object is read from or written to, redirecting the IO operation to the protocol rather than using the underlying IO accessor directly (i.e. mmap for a PCIe BAR).
* class: Attributes to control the instantiation of a protocol.
  * name: The name of the Python class to be instantiated. This class must inherit from `regio.regmap.io.methods.Protocol`.
  * args: A mapping of Python keyword arguments to be passed to the driver during instantiation.

A protocol view consist of the following attributes:
* name: The name of the virtual node for the indirect memory. Appears in the namespace of the parent decoder and must be unique within that scope.
* block: A reference to the block describing the regmap behind the indirect memory view. Is mutually exclusive with the decoder attribute.
* decoder: A reference to the decoder describing the regmap behind the indirect memory view. Is mutually exclusive with the block attribute.
* protocol: An optional definition of the protocol to use for accessing the view. When not specified, the protocol is taken from the controller block or decoder the view is attached to.
* class: Same structure as the class attribute for protocols. These attributes are merged with those from the protocol, replacing any existing ones and adding any new ones. This allows a protocol to be re-used by any views, while customizing it's run-time behaviour as needed.

Protocol Implementation
-----------------------
A protocol is implemented within a regular Python module containing a class derived from the `Protocol` base class exported by `regio.regmap.io.methods`. By means of a `!include` statement in the specification YAML, the `regio-elaborate` tool will read the entire contents of the file into the elaborated regmap, ensuring that the protocol is coupled with the register definitions. Any Python package dependencies required by the module will need to be installed separately on the running system prior to use of the generated `regio` tool.

The Python code listing below provides a skeleton for defining a custom protocol. Aside from the constructor, all methods are handed an IO proxy object to use for accessing the controller registers needed to implement the details of the protocol. The proxy references the regmap node for the target of the decoder interface that defined the view.
* If the interface targets a block, then the block's registers will be directly accessible from the proxy.
* If the interface targets a decoder, then the registers will be accessible from a child node that will be either a sub-decoder or a block.
```
#---------------------------------------------------------------------------------------------------
__all__ = (
    'Protocol',
)

from regio.regmap.io import methods

#---------------------------------------------------------------------------------------------------
class Protocol(methods.Protocol):
    # Override for custom instance initialization (OPTIONAL -- leave undefined if nothing to do).
    def __init__(self, spec, if_name, **kargs):
        # Perform custom instance initialization...
        super().__init__(spec, if_name) # Hand-off to base class.

    # Override for custom start sequence (OPTIONAL -- leave undefined if nothing to do).
    def start(self, proxy):
        # Perform custom start sequence...
        super().start(proxy) # Hand-off to base class.

    # Override for custom stop sequence (OPTIONAL -- leave undefined if nothing to do).
    def stop(self, proxy):
        # Perform custom stop sequence...
        super().stop(proxy) # Hand-off to base class.

    # Override for custom read operation (REQUIRED).
    def read(self, proxy, offset, size):
        # Perform protocol's read operation...
        value = 0
        return value # Return integer result.

    # Override for custom write operation (REQUIRED).
    def write(self, proxy, offset, size, value):
        # Perform protocol's write operation...
```

The `Protocol` base class also provides an `update` method, which performs a read/and-mask/or-mask/write sequence used for updating a bit field within a register. In most cases, the default implementation should be sufficient, but it can be overridden as well if needed. It's signature is as follows:
```
    # Override for custom update operation (OPTIONAL -- leave undefined if nothing to do).
    def update(self, proxy, offset, size, clr_mask, set_mask):
        # Perform a read operation at given offset...
        # Apply clr_mask to clear the bits being operated on.
        # Apply set_mask to set the bits being operated on.
        # Perform a write operation of the modified value to the given offset...
```
