#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections

# Name of the meta-data attribute set in all classes constructed by the Type meta-class (defined
# below) and all instances of those classes.
METADATA = '___metadata___'

#---------------------------------------------------------------------------------------------------
# Accessor for retrieving class or instance meta-data.
def data_get(obj):
    return getattr(obj, METADATA)

#---------------------------------------------------------------------------------------------------
class Data:
    def __init__(self, *pargs, **kargs):
        super().__init__()

    # Override this method to customize the meta-data attached to an instance.
    def new(self, obj, *pargs, **kargs):
        data = type(self)()
        data.members = self.members
        return data

#---------------------------------------------------------------------------------------------------
class Member:
    def __init__(self, name, value, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.name = name
        self.value = value

    def __call__(self, *pargs, **kargs):
        return type(self)(self.name, self.value(*pargs, **kargs))

#---------------------------------------------------------------------------------------------------
class Descriptor:
    def __init__(self, slot, *pargs, **kargs):
        super().__init__(*pargs, **kargs)
        self.slot = slot

    def __set_name__(self, cls, name):
        self.cls = cls
        self.name = name

    def __get__(self, obj, cls=None):
        if obj is None:
            obj = cls
        return data_get(obj).members[self.slot].value

    def __set__(self, obj, value):
        raise AttributeError(f'Attribute {self.name!r} on {self.cls!r} is read-only.')

    def __delete__(self, obj):
        raise AttributeError(f'Attribute {self.name!r} on {self.cls!r} is read-only.')

#---------------------------------------------------------------------------------------------------
class Namespace(collections.OrderedDict):
    def __init__(self, metacls, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Track the order in which attributes are created when the body of a class definition is
        # being executed during it's construction.
        self.metacls = metacls
        self.members = []

    def __setitem__(self, name, value):
        # An attribute is marked as a member when:
        # (1) A new instance of the meta-class is being constructed.
        # (2) The attribute being added to the namespace is a class object.
        # (3) The class object is also of the meta-class type (is an instance of the meta-class or
        #     one derived from it).
        if (self.metacls is not None and    # (1)
            self.metacls.is_typeof(value)): # (2) and (3)
            # Enforce uniqueness of member names. Without this check, duplicate names would over-
            # write the first definition in the namespace while taking up multiple slots in the
            # members list.
            if name in self:
                raise KeyError(f'Duplicate name {name!r} with value {value!r}.')

            # Track the order in which the member was defined.
            self.members.append(Member(name, value))
        super().__setitem__(name, value)

#---------------------------------------------------------------------------------------------------
class Type(type):
    @classmethod
    def is_typeof(metacls, obj):
        return (
            isinstance(obj, type) and      # Is a class?
            issubclass(type(obj), metacls) # Is it's meta-class of this type?
        )

    @classmethod
    def are_any_typeof(metacls, objects):
        for obj in objects:
            if metacls.is_typeof(obj):
                return True
        return False

    @classmethod
    def __prepare__(metacls, name, bases, *pargs, **kargs):
        return Namespace(metacls if metacls.are_any_typeof(bases) else None)

    def __new__(metacls, name, bases, ns, *pargs,
                metadata=None, metadesc=Descriptor, **kargs):
        # Determine which base classes are an instance (or derivative) of Type.
        metabases = tuple(b for b in bases if isinstance(b, Type))

        # Determine the type of the meta-data to be attached to the new class.
        metabase = None
        if metadata is None:
            # Use the first meta-base as the main type. Any subsequent bases are considered to be
            # mixin and only used for inheriting members and non-member attributes.
            if metabases:
                metabase = metabases[0]
                metadata = type(data_get(metabase))
            else:
                metadata = Data

        # Create and insert the meta-data into the new class namespace.
        data = metadata(metabase)
        data.members = tuple(ns.members)
        ns = dict(ns)
        ns[METADATA] = data

        # Create the new class object.
        # Note that __new__ eventually calls __init_subclass__ on all bases. Since the MRO field is
        # populated by __new__, the final members table will not yet be available for use (and the
        # function used for computing the MRO's linearization of the inheritance hierarchy isn't
        # exposed from any current built-in library). Instead, the new class must first be fully
        # constructed before accessing the linearization, so the __init_subclass__ calls will only
        # see the pre-merge members tables.
        cls = super().__new__(metacls, name, bases, ns, *pargs, **kargs)

        # Finalize the member table. Tables inherited from base classes are merged into a single one
        # for the new class.
        if metabases:
            data.members = metacls.merge_members(cls)

        # Create and attach a descriptor for each member.
        for slot, m in enumerate(data.members):
            super().__setattr__(cls, m.name, metadesc(slot))

        return cls

    @staticmethod
    def merge_members(cls):
        # Merge the member tables of all bases from the MRO's linearization of the class inheritance
        # hierarchy. Note that the linearization always includes the class itself as the first entry
        # in the sequence.
        #
        # Member tables are accumulated from oldest base to newest. Unknown members are appended to
        # the end of the merge table. Duplicate members are replaced by the newer one. If the base
        # class with the duplicate member name is a regular class (not an instance of the meta-
        # class), the member is marked as being shadowed and will be removed from the final table
        # unless re-enabled by a base occuring earlier in the MRO.
        class Entry: ...
        entries = {}
        for base in reversed(cls.__mro__):
            # The base is a regular class.
            if not isinstance(base, Type):
                # Find all member names shadowed by the base's attributes.
                names = set(vars(base))
                names.intersection_update(entries)

                # Mark the shadowed members for exclusion from the final table. A member may be
                # re-added by a subsequent base, in which case it will occupy the same slot in
                # the table.
                for name in names:
                    entries[name].shadowed = True

                continue

            # The base is an instance of the meta-class. Extract it's meta-data and merge it's
            # members.
            for bm in data_get(base).members:
                e = entries.get(bm.name)
                if e is None:
                    # Add the unknown member to the end of the table.
                    e = Entry()
                    e.slot = len(entries)
                    e.member = bm
                    e.shadowed = False

                    entries[bm.name] = e
                else:
                    # Replace the known member in the table. If the member slot was shadowed by an
                    # attribute in a regular base class, it is now re-enabled in the table.
                    e.member = bm
                    e.shadowed = False

        # Produce the final member table:
        # (1) Remove all members shadowed by an attribute in a regular base.
        # (2) Sort the remaining members by their slot in the merge table.
        members = tuple(
            e.member for e in sorted( # (2)
                filter(lambda e: not e.shadowed, entries.values()), # (1)
                key=lambda e: e.slot) # (2)
        )

        return members

#---------------------------------------------------------------------------------------------------
class Object(metaclass=Type):
    def __init__(self, *pargs, **kargs):
        # Create and attach meta-data to the new instance.
        super().__setattr__(METADATA, data_get(type(self)).new(self, *pargs, **kargs))
