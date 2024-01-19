#---------------------------------------------------------------------------------------------------
__all__ = ()

from . import tree
from ..types import meta

#---------------------------------------------------------------------------------------------------
# Accessor for retrieving class or instance meta-data.
def data_get(spec):
    return meta.data_get(spec)

#---------------------------------------------------------------------------------------------------
# The following is a list of attribute names that are writeable on all regmap types and instances.
# Regular attribute creation in the namespace of a class or instance is blocked in order to force a
# regmap specification into being read-only (as much as is possible in Python). Indirect access is
# granted by means of various proxies used for wrapping a regmap specification and operating on it
# sanely.
#
# Since a regmap specification describes a register hierarchy as implemented in hardware, any
# modifications would introduce errors, or worse, inconsistencies, that could be difficult to track
# down and resolve. The intent of restricting the namespace is to help catch common Python
# programming errors for users of the regmap. Lower level access is achievable by manipulating the
# structures hidden away under the meta.METADATA attribute (use at own risk!).
WRITEABLE = ()

#---------------------------------------------------------------------------------------------------
class Data(meta.Data):
    def __init__(self, metabase, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.config = None
        if metabase is None:
            self.config_cls = None
            self.node_cls = None
        else:
            # Use the info provided by the primary meta-base class.
            mdata = data_get(metabase)
            self.config_cls = mdata.config_cls
            self.node_cls = mdata.node_cls

    def new(self, spec, *pargs, **kargs):
        return self.node_cls(spec, self.members, self.config, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class Type(meta.Type):
    def __setattr__(cls, name, value):
        if name in WRITEABLE:
            super().__setattr__(name, value)
        else:
            raise AttributeError(f'Cannot set {name!r} attribute of type {metacls!r}.')

#---------------------------------------------------------------------------------------------------
class Object(meta.Object, metaclass=Type, metadata=Data):
    def __init_subclass__(cls, metainfo=None, **kargs):
        super().__init_subclass__()

        # Direct sub-class of Object is expected to specify metainfo and have no configuration.
        data = data_get(cls)
        if metainfo is not None:
            data.config_cls, data.node_cls = metainfo
            return

        # The sub-class doesn't support configuration.
        if data.config_cls is None:
            return

        # Find all bases that share Object's meta-class or one derived from it.
        bases = [b for b in cls.__mro__ if isinstance(b, Type)]

        # Accumulate inherited data from the bases.
        config_kargs = {}
        for base in reversed(bases):
            bdata = data_get(base)

            # Only inherit configuration from bases with the same meta-data type. This prevents
            # mixing configuration keywords while allowing members to be merged.
            if not issubclass(type(data), type(bdata)) or bdata.config is None:
                     continue

            # Accumulate configuration data over all bases. Data is merged such that data from the
            # tail of the MRO linearization are overridden by those closer to the head.
            config_kargs.update(bdata.config.changed_map)

        # Capture any extra keyword arguments given to the definition of the sub-class itself. This
        # data takes precedence over everything inherited by the bases.
        config_kargs.update(kargs)

        # Process the sub-class configuration.
        data.config = data.config_cls(cls, config_kargs)

    # TODO:
    # - Need option for lazy evaluation for efficient startup?
    # - Allow overriding configuration keywords?
    def __init__(self, name=None, parent=None, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Link the node into the parent's tree hierarchy or set it up as the root of it's own.
        node = data_get(self)
        node.name = type(self).__name__ if name is None else name
        pnode = tree.Root() if parent is None else data_get(parent)
        pnode.add(node)

    def __setattr__(self, name, value):
        if name in WRITEABLE:
            super().__setattr__(name, value)
        else:
            raise AttributeError(f'Cannot set {name!r} attribute of type {metacls!r}.')
