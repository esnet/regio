#---------------------------------------------------------------------------------------------------
__all__ = ()

#---------------------------------------------------------------------------------------------------
class Value:
    def __init__(self, relative, absolute, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.relative = relative
        self.absolute = absolute

    def inc(self, size):
        self.relative += size
        self.absolute += size

    def copy(self, *pargs, **kargs):
        return type(self)(*pargs, self.relative, self.absolute, **kargs)

#---------------------------------------------------------------------------------------------------
class Counter:
    def __init__(self, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.value = Value(0, 0)
        self.regions = []

    @property
    def size(self):
        return self.value.relative

    @property
    def current(self):
        return self.value.copy()

    def inc(self, size):
        self.value.inc(size)

    def align(self, size):
        offset = self.value.relative % size
        if offset > 0:
            self.inc(size - offset)

    def pause(self, reset=False):
        current = self.current
        self.regions.append(self.value)
        self.value = Value(0, 0 if reset else current.absolute)
        return current

    def restore(self):
        current = self.value
        self.value = self.regions.pop()
        return current.relative

    def restore_inc(self):
        size = self.restore()
        self.inc(size)
        return size
