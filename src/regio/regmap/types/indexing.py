#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc
import functools

#---------------------------------------------------------------------------------------------------
class KeyFieldRange:
    def __init__(self, indices, is_slice):
        self.indices = indices # Tuple of the form returned by the slice.indices method.
        self.start, self.stop, self.step = indices
        self.is_slice = is_slice

        # For convenience, the length spanned by the range is pre-calculated. This is done by using
        # the builtin range() to avoid duplicating the length calculation algorithm and to ensure
        # that the result is consistent with conventions. Refer to the following for details:
        # - https://docs.python.org/3/reference/expressions.html#slicings
        # - https://docs.python.org/3/reference/datamodel.html#slice-objects
        # - The get_len_of_range function in the cpython source contains the logic for how to use
        #   the output of the slice.indices method (implemented by _PySlice_GetLongIndices). To
        #   ensure the count calculated below is consistent with this convention, len() is used on a
        #   temporary throw-away range object rather than computing it directly from the slice.
        #   - https://github.com/python/cpython/blob/main/Objects/rangeobject.c#L933
        #   - https://github.com/python/cpython/blob/main/Objects/sliceobject.c#L405
        self.length = len(range(*indices))

    def __len__(self):
        return self.length

    def _iter(self, reversed_=False):
        range_ = range(*self.indices)
        return reversed(range_) if reversed_ else iter(range_)

    def __iter__(self):
        return self._iter(False)

    def __reversed__(self):
        return self._iter(True)

#---------------------------------------------------------------------------------------------------
class KeyFieldRangeList:
    def __init__(self, ranges):
        self.ranges = ranges
        self.length = sum(r.length for r in ranges)
        self.is_slice = len(ranges) > 1 or ranges[0].is_slice

    def __len__(self):
        return self.length

    def _iter(self, reversed_=False):
        iter_fn = reversed if reversed_ else iter
        for range_ in iter_fn(self.ranges):
            for idx in iter_fn(range_):
                yield idx

    def __iter__(self):
        return self._iter(False)

    def __reversed__(self):
        return self._iter(True)

#---------------------------------------------------------------------------------------------------
class Key:
    def __init__(self, indexer, fields):
        self.indexer = indexer

        # A key must always have the full set of fields to match the indexer. Capturing the number
        # of unprocessed fields passed in allows signalling that the key was seeded with a partial
        # set of fields, making it possible to build up a full key iteratively. Each missing field
        # will be padded out to be a single slice over it's the entire range during processing by
        # the Key.to_ranges method. The unprocessed fields are also captured for use in subsequent
        # extension operations using the Key.extend method to build a new from this one as a basis.
        self.nfields = len(fields)
        self.fields = tuple(fields)

        # Canonicalize each given field as a sequence of one or more ranges. This allows leveraging
        # the slice list syntax (x[i,j:k,m]) to specify an arbirary ordering for iteration, which
        # includes repeating ranges.
        self.ranges = self.to_ranges(fields)
        self.length = functools.reduce(lambda res, r: res * r.length, self.ranges, 1)
        self.is_slice = any(r.is_slice for r in self.ranges)

    def extend(self, fields):
        # Extend the set of fields of the current key with ranges for missing fields. A single field
        # is specified as a sequence of ranges. A range is either a single integer or a slice. The
        # argument is first re-formatted to put it into a consistent form needed for canonicalizing
        # the ranges. For each field, the expected form should be field=(range0, range1, ...), where
        # the argument is fields=(field0, field1, ...). This sequence will be appended to the end of
        # the current key's captured set.
        if isinstance(fields, collections.abc.Sequence):
            # The input was already in sequence form, so wrap any non-sequence elements.
            fields = tuple(
                field if isinstance(field, collections.abc.Sequence) else (field,)
                for field in fields
            )
        else:
            # The input is a singular item, so treat it as a single range for a single field.
            fields = ((fields,),)

        # Extend the current key's fields in preparation for building a new key.
        fields = self.fields + fields

        # Make sure the maximum number of fields is respected. Missing fields will be interpreted as
        # a slice over the field's entire range, but too many fields is an error.
        nfields = len(fields)
        if nfields > self.indexer.nfields:
            raise TypeError(f'Key too long. Got {nfields}, expected {self.indexer.nfields}.')

        # Build a new key for the extension.
        return self.indexer.new_key(fields)

    def to_ranges(self, fields):
        # Pad out the missing fields with a single slice over the entire range.
        nfields = len(fields)
        if nfields < self.indexer.nfields:
            fields += tuple([(slice(None, None, 1),)] * (self.indexer.nfields - nfields))

        # Canonicalize the ranges and wrap them up into convenience objects for use in iteration.
        return tuple(
            self.to_range_list(ranges, length)
            for ranges, length in zip(fields, self.indexer.fields)
        )

    def to_range_list(self, ranges, length):
        # Validate each range against the field's length and produce indices for iteration with the
        # builtin range().
        return KeyFieldRangeList(tuple(self.to_range(range_, length) for range_ in ranges))

    def to_range(self, range_, length):
        if isinstance(range_, slice):
            # By Python convention, slices are not range checked. The range defined by a slice is
            # clipped to fit within the bounds of the sequence or simply resolved to empty.
            return KeyFieldRange(range_.indices(length), True)

        if isinstance(range_, int):
            # By Python convention, a negative index is treated as being relative to the end of the
            # sequence. Refer to https://docs.python.org/3/reference/expressions.html#subscriptions
            if range_ < 0:
                range_ += length

            if 0 <= range_ < length:
                # (start, stop, step) tuple as returned by the slice.indices method.
                return KeyFieldRange((range_, range_ + 1, 1), False)

            # Invalid range.
            raise IndexError(f'Field index {range_!r} is out of range [0,{length}).')

        # Invalid type.
        raise TypeError(f'Field range {range_!r} must be either an integer or slice.')

    @property
    def is_partial(self):
        return self.nfields < self.indexer.nfields

    @property
    def first(self):
        return tuple(r.ranges[0].start for r in self.ranges)

    def to_ordinal(self, index):
        return self.indexer.to_ordinal(index)

    def from_ordinal(self, ordinal):
        return self.indexer.from_ordinal(ordinal)

    def __len__(self):
        return self.length

    def _iter(self, reversed_=False):
        return self.indexer.iter_key(self, reversed_)

    def iter_ordinal(self, reversed_=False):
        for index in self._iter(reversed_):
            yield self.indexer._to_ordinal(index)

    def __iter__(self):
        return self._iter(False)

    def __reversed__(self):
        return self._iter(True)

#---------------------------------------------------------------------------------------------------
class KeyIterator:
    def __init__(self, key, reversed_):
        self._key = key

        # Create and start an iterator over the ranges of each field.
        iter_fn = reversed if reversed_ else iter
        iters = [iter_fn(r) for r in self._key.ranges]

        # Set the cursor to the first index.
        try:
            cursor = [next(it) for it in iters]
        except StopIteration:
            # Handle empty ranges.
            self._cursor = None
        else:
            self._iter_fn = iter_fn
            self._iters = iters
            self._cursor = cursor

    def __iter__(self):
        # Iterators are consumable, so no need to handle restarting.
        return self

    def __next__(self):
        cursor = self._cursor

        # The iterator has been exhausted.
        if cursor is None:
            raise StopIteration

        # Capture the index for this iteration.
        index = tuple(cursor)

        # Advance the cursor for the next iteration according to the indexer's increment ordering.
        iter_fn = self._iter_fn
        iters = self._iters
        ranges = self._key.ranges
        for field in self._key.indexer.inc_order:
            try:
                # Update the range iterator for the next field to be incremented.
                cursor[field] = next(iters[field])
            except StopIteration:
                # Restart the iterator on the field before advancing to the next one.
                iters[field] = iter_fn(ranges[field])
                cursor[field] = next(iters[field])
            else:
                # The cursor is set for the next iteration cycle.
                break
        else:
            # The ranges have all been traversed.
            del self._iters
            self._cursor = None # In case next() is called afterwards.

        return index

#---------------------------------------------------------------------------------------------------
class Indexer:
    def __init__(self, fields, *pargs, **kargs):
        super().__init__(*pargs, **kargs)

        self.nfields = len(fields)
        if self.nfields < 1:
            raise AssertionError('Missing fields.')

        # Each field is specified as a pair of the form (length, increment_order).
        self.fields = tuple(length for length, _ in fields)
        self.inc_order = tuple(order for _, order in fields)

        # Compute the span covered by a unit increment in each field.
        self.spans = [1] * self.nfields
        for prev, field in zip(self.inc_order[:-1], self.inc_order[1:]):
            self.spans[field] = self.spans[prev] * self.fields[prev]

        # Total number of indexable elements spanned by the length of the fields.
        self.length = self.spans[-1] * self.fields[-1]

    def _to_ordinal(self, index):
        # Reduce the given index to a single integer ordinal.
        return sum(span * idx for span, idx in zip(self.spans, index))

    def to_ordinal(self, index):
        # The index must have a component for each field.
        if len(index) != self.nfields:
            raise IndexError(f'Index {index!r} has {len(index)} fields, expected {self.nfields}.')

        # Range check each component of the index against it's respective field's length. Note that
        # negative values are not supported in an index, only key fields can be negative, but must
        # be converted to a valid range using Key.to_range.
        if any(idx < 0 or idx >= length for idx, length in zip(index, self.fields)):
            raise IndexError(f'Index {index!r} is out of range.')

        return self._to_ordinal(index)

    def _from_ordinal(self, ordinal):
        # Expand the ordinal into an index with a component for each field.
        rem = ordinal
        index = [None] * self.nfields
        for field in reversed(self.inc_order):
            index[field], rem = divmod(rem, self.spans[field])
        return tuple(index)

    def from_ordinal(self, ordinal):
        # The ordinal must be within the range of indexable elements.
        if ordinal >= self.length:
            raise ValueError(f'Ordinal {ordinal} exceeds range [0,{self.length}).')

        return self._from_ordinal(ordinal)

    # Override to replace the key type.
    def new_key(self, fields):
        return Key(self, fields)

    # Override to replace the key iterator type.
    def iter_key(self, key, reversed_=False):
        return KeyIterator(key, reversed_)

    def iter_all(self, reversed_=False):
        return self.iter_key(self.new_key(()), reversed_)

    def __len__(self):
        return self.length

    def __iter__(self):
        return self.iter_all(False)

    def __reversed__(self):
        return self.iter_all(True)

#---------------------------------------------------------------------------------------------------
class CArrayIndexer(Indexer):
    def __init__(self, dimensions, *pargs, **kargs):
        # The indices in a C-style array are incremented from the last dimension to the first, such
        # that for x[a][b][c], an index has the form (a, b, c) and the increment order is (2, 1, 0),
        # meaning c first, then b and finally a.
        fields = tuple(zip(dimensions, reversed(range(len(dimensions)))))
        super().__init__(fields, *pargs, **kargs)
