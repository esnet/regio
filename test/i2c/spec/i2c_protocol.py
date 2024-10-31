#---------------------------------------------------------------------------------------------------
__all__ = (
    'I2cClientProtocol',
    'I2cControllerProtocol',
    'I2cMuxChannelProtocol',
    'I2cMuxProtocol',
)

from regio.regmap.io import methods

#---------------------------------------------------------------------------------------------------
class I2cControllerProtocol(methods.Protocol):
    def transact(self, proxy, txn):
        ...

#---------------------------------------------------------------------------------------------------
class I2cClientProtocol(methods.Protocol):
    def read(self, proxy, offset, size):
        return 0

    def write(self, proxy, offset, size, value):
        ...

#---------------------------------------------------------------------------------------------------
class I2cMuxProtocol(methods.Protocol):
    def transact(self, proxy, txn):
        ...

#---------------------------------------------------------------------------------------------------
class I2cMuxChannelProtocol(methods.Protocol):
    def transact(self, proxy, txn):
        ...
