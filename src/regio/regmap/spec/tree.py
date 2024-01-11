#---------------------------------------------------------------------------------------------------
__all__ = ()

from ..types import tree

#---------------------------------------------------------------------------------------------------
class Base(tree.Node):
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.name = ''
        self.path = ()

    def attach(self, parent):
        super().attach(parent)

        # Set the node's path in the hierarchy.
        self.path = parent.path + (self.name,)

    def detach(self):
        raise NotImplementedError

    def qualname_from(self, start):
        return '.'.join(self.path[start:])

    @property
    def qualname(self):
        return self.qualname_from(0)

#---------------------------------------------------------------------------------------------------
class Root(Base): ...

#---------------------------------------------------------------------------------------------------
class Node(Base):
    def __init__(self, spec, members, config, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.spec = spec
        self.members = members
        self.members_map = {}
        self.config = config
        self.region = None

    def attach(self, parent):
        super().attach(parent)

        # Instantiate the members within the instance's class namespace.
        self.members_init()

    def members_init(self):
        self.members = tuple(m(m.name, self.spec) for m in self.members)
        self.members_map = dict((m.name, m) for m in self.members)
