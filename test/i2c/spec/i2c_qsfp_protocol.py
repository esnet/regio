#---------------------------------------------------------------------------------------------------
__all__ = (
    'I2cQsfpClientProtocol',
    'I2cQsfpControllerProtocol',
    'I2cQsfpFlatProtocol',
)

from regio.regmap.io import methods

#---------------------------------------------------------------------------------------------------
class I2cQsfpControllerProtocol(methods.Protocol):
    def transact(self, proxy, txn):
        ...

#---------------------------------------------------------------------------------------------------
class I2cQsfpClientProtocol(methods.Protocol):
    def read(self, proxy, offset, size):
        return 0

    def write(self, proxy, offset, size, value):
        ...

#---------------------------------------------------------------------------------------------------
class I2cQsfpFlatProtocol(methods.Protocol):
    def read(self, proxy, offset, size):
        return 0

    def write(self, proxy, offset, size, value):
        ...
