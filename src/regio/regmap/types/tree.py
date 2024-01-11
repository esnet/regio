#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc

#---------------------------------------------------------------------------------------------------
class Node:
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.parent = None
        self.children = []

    def attach(self, parent):
        if self.parent is not None:
            self.parent.remove_child(self)
        self.parent = parent

    def add_child(self, node):
        self.children.append(node)
        node.attach(self)

    def add(self, children):
        if not isinstance(children, collections.abc.Iterable):
            children = [children]

        for node in children:
            self.add_child(node)

    def detach(self):
        self.parent = None

    def remove_child(self, node):
        node.detach()
        self.children.remove(node)

    def remove(self, children):
        if not isinstance(children, collections.abc.Iterable):
            children = [children]

        for node in children:
            self.remove_child(node)

    def clear(self):
        while self.children:
            self.remove_child(self.children[0])

    @property
    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    @property
    def descendants(self):
        for node in self.children:
            yield node

            for dnode in node.descendants:
                yield dnode

    @property
    def siblings(self):
        if self.parent is None:
            raise StopIteration

        for node in self.parent.children:
            yield node
