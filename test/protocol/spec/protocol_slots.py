#---------------------------------------------------------------------------------------------------
__all__ = (
    'BusClientProtocol',
    'BusControllerProtocol',
    'Protocol',
)

import math

from regio.regmap.io import methods
from regio.regmap.spec import info

#---------------------------------------------------------------------------------------------------
# Expects the parent controller to contain an array of registers named "slots" that is properly
# sized to accommodate all the registers contained within the indirect view (including all nested
# views that may be defined). Each view can optionally specify the protocol's "slot_width" argument,
# which will apply a right bit-shift to the offset to extract a base index into the "slots" array
# where the first register starts. This allows compressing the register offsets into a smaller set
# of slots.
class Protocol(methods.Protocol):
    def __init__(self, spec, if_name, slot_width=0, **kargs):
        super().__init__(spec, if_name)

        # Adjust the slot bit width of the byte address to data words.
        if slot_width > 0:
            octets = (info.data_width_of(spec) + 8 - 1) // 8
            shift = math.ceil(math.log2(octets))
            slot_width -= shift

        self.slot_width = slot_width
        self.slot_mask = (1 << self.slot_width) - 1
        self.kargs = kargs

        self._tag = f'{type(self).__name__}:{info.qualname_of(spec)}'
        print(f'# INIT[{self._tag}]: '
              f'Initializing with slot_width={slot_width}, kargs={kargs!r}.')

    def _offset_to_slot(self, offset):
        return (offset >> self.slot_width) + (offset & self.slot_mask)

    def read(self, proxy, offset, size):
        slot = self._offset_to_slot(offset)
        print(f'# READ[{self._tag}]: '
              f'offset 0x{offset:x} for {size} words '
              f'=> mapped to controller slot {slot}.')

        # Read the value from the appropriate slot in the parent controller's registers.
        return int(proxy.slots[slot]._r)

    def write(self, proxy, offset, size, value):
        slot = self._offset_to_slot(offset)
        print(f'# WRITE[{self._tag}]: '
              f'value 0x{value:x} to offset 0x{offset:x} for {size} words '
              f'=> mapped to controller slot {slot}.')

        # Write the value into the appropriate slot in the parent controller's registers.
        proxy.slots[slot]._r = value

#---------------------------------------------------------------------------------------------------
class BusTransaction(methods.Transaction):
    def __init__(self, slot, value=None):
        super().__init__(None, value)
        self.slot = slot

#---------------------------------------------------------------------------------------------------
class BusControllerProtocol(methods.Protocol):
    def __init__(self, spec, if_name, **kargs):
        super().__init__(spec, if_name)

        self.kargs = kargs
        self._tag = f'{type(self).__name__}:{info.qualname_of(spec)}'
        print(f'# INIT[{self._tag}]: Initializing with kargs={kargs!r}.')

    # Override the higher level method for processing all transactions sent to the controller. The
    # controller expects to only handle transactions from clients. The clients are responsible for
    # ensuring that the appropriate bit-shifting and masking is performed, allowing the controller
    # to simply access a register as a whole without dealing with fields.
    def transact(self, proxy, txn):
        if not isinstance(txn, BusTransaction):
            raise TypeError(f'Expected transaction of type {BusTransaction!r}, got {type(txn)!r}.')

        # Perform the transaction on the appropriate slot in the parent controller's registers.
        slot = txn.region.offset.absolute + txn.slot
        if txn.value is None:
            print(f'# TRANSACT[{self._tag}]: '
                  f'reading from controller slot {slot}.')
            txn.value = int(proxy.slots[slot]._r)
        else:
            print(f'# TRANSACT[{self._tag}]: '
                  f'writting value 0x{txn.value:x} to controller slot {slot}.')
            proxy.slots[slot]._r = txn.value

#---------------------------------------------------------------------------------------------------
class BusClientProtocol(methods.Protocol):
    def __init__(self, spec, if_name, **kargs):
        super().__init__(spec, if_name)

        self.kargs = kargs
        self._tag = f'{type(self).__name__}:{info.qualname_of(spec)}'
        print(f'# INIT[{self._tag}]: Initializing with kargs={kargs!r}.')

    def read(self, proxy, offset, size):
        print(f'# READ[{self._tag}]: '
              f'offset 0x{offset:x} for {size} words.')

        # Send a read transaction to the controller.
        txn = BusTransaction(offset)
        proxy.transact = txn
        return txn.value

    def write(self, proxy, offset, size, value):
        print(f'# WRITE[{self._tag}]: '
              f'value 0x{value:x} to offset 0x{offset:x} for {size} words.')

        # Send a write transaction to the controller.
        proxy.transact = BusTransaction(offset, value)
