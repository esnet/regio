#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc
import functools

#---------------------------------------------------------------------------------------------------
class Key:
    def __init__(self, indexer, fields):
        self.indexer = indexer
        self.fields = tuple(fields)
        self.nfields = len(fields)
        self.ranges = self.to_ranges(fields)
        self.length = functools.reduce(lambda res, range_: res * range_[1], self.ranges, 1)

    def extend(self, fields):
        # Extend the key's fields.
        if not isinstance(fields, collections.abc.Sequence):
            fields = (fields,)
        fields = self.fields + fields

        # Make sure the maximum number of fields is respected. Missing fields will be interpreted as
        # a slice over the field's entire range.
        nfields = len(fields)
        if nfields > self.indexer.nfields:
            raise TypeError(f'Key too long. Got {nfields}, expected {self.indexer.nfields}.')

        # Build a new key for the extension.
        return self.indexer.new_key(fields)

    def to_ranges(self, fields):
        # Pad the fields with slices over each missing field's entire range.
        nfields = len(fields)
        if nfields < self.indexer.nfields:
            fields += tuple([slice(None, None, 1)] * (self.indexer.nfields - nfields))

        # Translate each field into a range tuple of the form (indices, length), where indices is
        # of the form (start, stop, step) (as returned by slice.indices and accepted as arguments
        # to the range constructor).
        return tuple(
            self.to_range(field, length)
            for field, length in zip(fields, self.indexer.fields)
        )

    @staticmethod
    def to_range(field, length):
        if isinstance(field, slice):
            # By Python convention, slices are not range checked. The range defined by a slice is
            # clipped to fit within the bounds of the sequence or simply resolved to being empty.
            #
            # For convenience, the length spanned by the range is included. This is done by using
            # the builtin "range" to avoid duplicating the length calculation algorithm and to
            # ensure that the result is consistent with conventions. Refer to:
            # - https://docs.python.org/3/reference/expressions.html#slicings
            # - https://docs.python.org/3/reference/datamodel.html#slice-objects
            # - The get_len_of_range function in the cpython source contains the logic for how to
            #   use the output of the slice.indices method (implemented by _PySlice_GetLongIndices).
            #   To ensure the count calculated below is consistent with this convention, use len on
            #   a temporary range object rather than computing it directly from the slice.
            #   - https://github.com/python/cpython/blob/main/Objects/rangeobject.c#L933
            #   - https://github.com/python/cpython/blob/main/Objects/sliceobject.c#L405
            indices = field.indices(length)
            return (indices, len(range(*indices))) # (indices=(start, stop, step), length)

        if isinstance(field, int):
            # By Python convention, a negative index is treated as being relative to the end of the
            # sequence. Refer to https://docs.python.org/3/reference/expressions.html#subscriptions
            if field < 0:
                field += length

            if 0 <= field < length:
                return ((field, field + 1, 1), 1) # (indices=(start, stop, step), length)

            # Invalid range.
            raise IndexError(f'Field {field!r} is out of range [0,{length}).')

        # Invalid type.
        raise TypeError(f'Field {field!r} must be either an integer or slice.')

    @property
    def start(self):
        return tuple(indices[0] for indices, _ in self.ranges)

    def to_ordinal(self, index):
        return self.indexer.to_ordinal(index)

    def from_ordinal(self, ordinal):
        return self.indexer.from_ordinal(ordinal)

    def __len__(self):
        return self.length

    def __iter__(self):
        return self.indexer.iter_key(self, False)

    def __reversed__(self):
        return self.indexer.iter_key(self, True)

#---------------------------------------------------------------------------------------------------
class KeyIterator:
    def __init__(self, key, reversed_):
        self._key = key

        # Create and start a range iterator for each field, where a range is of the form defined by
        # Key.to_range: (indices=(start, stop, step), length).
        iter_fn = reversed if reversed_ else iter
        iters = [iter_fn(range(*indices)) for indices, _ in self._key.ranges]

        # Set the cursor to the start index.
        try:
            cursor = [next(i) for i in iters]
        except StopIteration:
            # Handle empty ranges.
            self._cursor = ()
        else:
            self._iter_fn = iter_fn
            self._iters = iters
            self._cursor = cursor

    def __iter__(self):
        # Iterators are consumable, so no need to handle restarting.
        return self

    def __next__(self):
        # The iterator has been exhausted.
        if len(self._cursor) < 1:
            raise StopIteration

        # Capture the index for this iteration.
        index = tuple(self._cursor)

        # Advance the cursor for the next iteration according to the indexer's increment ordering.
        for field in self._key.indexer.inc_order:
            try:
                # Update the range iterator.
                self._cursor[field] = next(self._iters[field])
            except StopIteration:
                # Restart the iterator on the field before advancing to the next one.
                self._iters[field] = self._iter_fn(range(*self._key.ranges[field][0]))
                self._cursor[field] = next(self._iters[field])
            else:
                break
        else:
            # The ranges have all been traversed.
            del self._iters
            self._cursor = () # In case next() is called afterwards.

        return index

#---------------------------------------------------------------------------------------------------
class Indexer:
    def __init__(self, fields, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        # Each field is specified as a pair of the form (length, increment_order).
        self.nfields = len(fields)
        self.fields = tuple(length for length, _ in fields)
        self.inc_order = tuple(order for _, order in fields)

        # Compute the span covered by a unit increment in each field.
        self.spans = [1] * self.nfields
        for prev, field in zip(self.inc_order[:-1], self.inc_order[1:]):
            self.spans[field] = self.spans[prev] * self.fields[prev]

        # Total number of indexable elements.
        self.length = self.spans[-1] * self.fields[-1]

    def new_key(self, fields):
        return Key(self, fields)

    def to_ordinal(self, index):
        # The index must have a component for each field.
        if len(index) != self.nfields:
            raise IndexError(f'Index {index!r} has {len(index)} fields, expected {self.nfields}.')

        # Range check each component of the index against it's respective field's length. Note that
        # negative values are not supported in an index, only key fields can be negative, but must
        # be converted to a valid range using Key.to_range.
        if any(idx < 0 or idx >= length for idx, length in zip(index, self.fields)):
            raise IndexError(f'Index {index!r} is out of range.')

        # Reduce the given index to a single integer ordinal.
        return sum(span * idx for span, idx in zip(self.spans, index))

    def from_ordinal(self, ordinal):
        # The ordinal must be within the range of indexable elements.
        if ordinal >= self.length:
            raise ValueError(f'Ordinal {ordinal} exceeds range [0,{self.length}).')

        # Expand the ordinal into an index with a component for each field.
        rem = ordinal
        index = [None] * self.nfields
        for field in reversed(self.inc_order):
            index[field], rem = divmod(rem, self.spans[field])
        return tuple(index)

    def iter_key(self, key, reversed_):
        return KeyIterator(key, reversed_)

    def iter_all(self, reversed_):
        return self.iter_key(self.new_key(()), reversed_)

    def __iter__(self):
        return self.iter_all(False)

    def __reversed__(self):
        return self.iter_all(True)

    def __len__(self):
        return self.length

#---------------------------------------------------------------------------------------------------
class CArrayIndexer(Indexer):
    def __init__(self, dimensions, *pargs, **kargs):
        # The indices in a C-style array are incremented from the last dimension to the first, such
        # that for x[a][b][c], an index has the form (a, b, c) and the increment order is (2, 1, 0),
        # meaning c first, then b and finally a.
        fields = tuple(zip(dimensions, reversed(range(len(dimensions)))))
        super().__init__(fields, *pargs, **kargs)
