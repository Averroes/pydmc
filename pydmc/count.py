"""
Different ways to count things.

Iterators
---------
iter_subset(objs, k)    -- all subsets of objs with k elements
iter_multiset(objs, k)  -- all multisets of objs with k elements.
                           Elements can be repeated.
iter_symmetric(shape, symmetries)
                        -- indices with the given symmetries
iter_indices(shape)     -- indices with each index running over the given
                           range in the tuple shape.
iter_count_in_base(base, ndigits)
                        -- tuples of length ndigits with integer
                           indices in [0,base)
permutations(objs)      -- all permutations of elements of objs
combinations(objs, k)   -- all combinations of elements of objs taken k
                            at a time. This is the same as iter_subsets.

Combinatorics
-------------
factorial(n)            -- n!
binomial(n,k)           -- binomial coefficient nCk
multinomial((n1,n2,...,nk))
                        -- multinomial coefficient
count_permutations(lst) -- count the number of permutations of elements in lst

count_permutations2(a,b)
count_permutations3(a,b,c)
count_permutations4(a,b,c,d)
                        -- optimized versions of count_permutations for
                           2, 3, and 4 elements.

Sorting small sequences
-----------------------
sort2(a,b)              -- return (a,b) in sorted order
sort3(a,b,c)            -- return (a,b,c) in sorted order
sort4(a,b,c,d)          -- return (a,b,c,d) in sorted order
sort2_int, sort3_int, sort4_int -- same as sort?, but specialized for integers
                                   only
"""
__all__ = ['iter_subset', 'iter_multiset', 'iter_symmetric',
           'iter_indices', 'iter_count_in_base',
           'permutations', 'combinations',
           'factorial', 'binomial', 'multinomial', 'count_permutations']

import warnings
from pydmc import _count, bindconstants

class _KSomeset(object):
    def __init__(self, objs, k):
        object.__init__(self)
        try:
            n = len(objs)
        except:
            n = int(objs)
            objs = range(0, n)
        self.n = n
        self.objs = objs
        self.k = k

    def __len__(self):
        # len() doesn't like __len__ methods that return a long, so cast to int
        return int(self.length())

class iter_subset(_KSomeset):
    """Iterator for subsets of a given length.

    Example:

    >>> list(iter_subset(4, 3))
    [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]
    >>> [''.join(s) for s in iter_subset("abcde", 3)]
    ['abc', 'abd', 'abe', 'acd', 'ace', 'ade', 'bcd', 'bce', 'bde', 'cde']
    """
    def __init__(self, objs, k):
        """Create an iterator over subsets of a given length.

        objs:   sequence to form subsets from.
                May be an integer, then range(objs) is used.
        k:      length of subsets
        """
        _KSomeset.__init__(self, objs, k)

    def __iter__(self):
        n = self.n
        k = self.k
        if k <= 0 or n <= 0 or n < k:
            return iter([()])
        limits = [n-k+i+1 for i in range(0,k) ]
        index_map = [0] + range(0, k-1)
        increments = [1] * k
        return _count.LexicographicIterator(self.objs, limits,
                                            index_map, increments)

    def length(self):
        return binomial(self.n, self.k)

def combinations(objs, k):
    """Iterator for all combinations of objs taken k at a time.
    If objs is an integer, range(objs) is used.

    This is the same as iter_subset.
    """
    return iter_subset(objs, k)

def _test_Subset():
    results = [ [(1,1), (0,)],
                [(2,0), ()],
                [(2,1), (0,), (1,)],
                [(2,2), (0,1)],
                [(3,0), ()],
                [(3,1), (0,), (1,), (2,)],
                [(3,2), (0,1), (0,2), (1,2)],
                [(3,3), (0,1,2)],
                [(5,3), (0,1,2), (0,1,3), (0,1,4), (0,2,3), (0,2,4),
                        (0,3,4), (1,2,3), (1,2,4), (1,3,4), (2,3,4)],
                [(('a','b','c'),2),
                 ('a', 'b'), ('a', 'c'), ('b','c')],
              ]
    for r in results:
        n,k = r[0]
        r = r[1:]
        routine_result = list(iter_subset(n,k))
        assert routine_result == r, (n,k,routine_result)

    assert len(iter_subset(20,5)) == 15504

class MultisetIterator(_KSomeset):
    """Iterator over the multisets of length k.

    A multiset is a subset with repeated members.

    Example:

    >>> list(iter_multiset(3, 2))
    [(0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2)]
    >>> [''.join(s) for s in iter_multiset("abc", 3)]
    ['aaa', 'aab', 'aac', 'abb', 'abc', 'acc', 'bbb', 'bbc', 'bcc', 'ccc']
    """
    def __init__(self, objs, k):
        """Create an iterator over the multisets of objs of length k.

        objs:   sequence to form multisets from
                May be an integer, then range(objs) is used.
        k:      length of multisets
        """
        _KSomeset.__init__(self, objs, k)

    def __iter__(self):
        n = self.n
        k = self.k
        if k <= 0 or n <= 0:
            return iter([()])
        limits = [n] * k
        index_map = [ i-1 for i in range(0,k) ]
        increments = [0] * k
        return _count.LexicographicIterator(self.objs, limits,
                                            index_map, increments)

    def length(self):
        return binomial(self.n + self.k - 1, self.k)

def iter_multiset(objs, k):
    return MultisetIterator(objs, k)
iter_multiset.__doc__ = MultisetIterator.__doc__

def _test_Multiset():
    results = [ [(0,0), ()],
                [(1,0), ()],
                [(1,1), (0,)],
                [(1,2), (0,0)],
                [(3,3), (0,0,0), (0,0,1), (0,0,2), (0,1,1), (0,1,2),
                        (0,2,2), (1,1,1), (1,1,2), (1,2,2), (2,2,2)],
                [("abc",2), ('a','a'), ('a','b'), ('a','c'),
                            ('b','b'), ('b','c'), ('c','c')],
              ]
    for r in results:
        n,k = r[0]
        r = r[1:]
        routine_result = list(iter_multiset(n,k))
        assert routine_result == r, (n,k,routine_result)

    assert len(iter_multiset(20,5)) == 42504

class SymmetricIndicesIterator:
    def __init__(self, shape, symmetries):
        self.shape = shape
        self.symmetries = symmetries
        if len(shape) != len(symmetries):
            raise ValueError, "Must describe symmetries for all indices"
        self._create_sym_map()

    def __iter__(self):
        k = len(self.shape)
        if k == 0:
            return iter([()])
        increments = (0,) * k
        objs = range(max(self.shape))
        return _count.LexicographicIterator(objs, self.shape,
                                            self._index_map, increments)

    def _create_sym_map(self):
        shape = self.shape
        k = len(shape)
        self._index_map = index_map = [0]*k
        self._sym_map = sym_map = {}
        if k == 0:
            return
        for i, s in enumerate(self.symmetries):
            if s in sym_map:
                # seen this one -- don't reset, use previous index
                last_i = sym_map[s][-1]
                if shape[i] != shape[last_i]:
                    raise ValueError(
                       "symmetric indices %d and %d don't have the same dimension"
                       % (last_i, i))
                index_map[i] = last_i
                sym_map[s].append(i)
            else:
                sym_map[s] = [i]
                index_map[i] = -1

    def __len__(self):
        N = 1
        for s, indices in self._sym_map.items():
            n = self.shape[indices[0]]
            k = len(indices)
            N *= binomial(n+k-1, k)
        return int(N)

def iter_symmetric(shape, symmetries=None):
    """Iterator over indices with the specified symmetry.

    For example: if the matrix A[i,j,k,l] is such that it is symmetric wrt
    i and l, and wrt j and k, we can do

    >>> for T in iter_symmetric(A.shape, "abba"):
    ...     A[T]
    """
    if symmetries is None:
        symmetries = (0,) * len(shape)
    return SymmetricIndicesIterator(shape, symmetries)

def _test_iter_symmetric():
    def abba_iter(n):
        for t0 in range(0,n):
            for t1 in range(0,n):
                for t2 in range(t1, n):
                    for t3 in range(t0,n):
                        yield (t0, t1, t2, t3)
    n = 3
    abba = list(abba_iter(n))
    assert abba == list(iter_symmetric((n,n,n,n), "abba"))

def iter_indices(shape):
    """Iterator to count numbers with mixed bases.

    Useful for iterating over the elements of a multidimensional array.
    """
    k = len(shape)
    if k == 0:
        return iter([()])
    index_map = (-1,)*k
    increments = (0,)*k
    return _count.LexicographicIterator(range(max(shape)), shape, index_map,
                                        increments)

def count_with_bases(shape):
    """Deprecated -- use iter_indices instead"""
    warnings.warn('count_with_bases -- use iter_indices instead',
                  DeprecationWarning,
                  stacklevel=2)
    return iter_indices(shape)

def _test_count_with_bases():
    counts = [ c for c in iter_indices((2,3,4)) ]
    assert counts == [
        (0,0,0), (0,0,1), (0,0,2), (0,0,3),
        (0,1,0), (0,1,1), (0,1,2), (0,1,3),
        (0,2,0), (0,2,1), (0,2,2), (0,2,3),
        (1,0,0), (1,0,1), (1,0,2), (1,0,3),
        (1,1,0), (1,1,1), (1,1,2), (1,1,3),
        (1,2,0), (1,2,1), (1,2,2), (1,2,3),
    ], counts

def iter_count_in_base(base, ndigits):
    """Iterator to count numbers in a base, with ndigits per number (as tuples)."""
    return iter_indices([base]*ndigits)

def count_in_base(base, ndigits):
    """Deprecated -- use iter_count_in_base instead"""
    warnings.warn('count_in_base -- use iter_count_in_base instead',
                  DeprecationWarning,
                  stacklevel=2)
    return iter_count_in_base(base, ndigits)

def _test_count_in_base():
    counts = [ c for c in iter_count_in_base(3,3) ]
    assert counts == [
                       (0,0,0), (0,0,1), (0,0,2),
                       (0,1,0), (0,1,1), (0,1,2),
                       (0,2,0), (0,2,1), (0,2,2),
                       (1,0,0), (1,0,1), (1,0,2),
                       (1,1,0), (1,1,1), (1,1,2),
                       (1,2,0), (1,2,1), (1,2,2),
                       (2,0,0), (2,0,1), (2,0,2),
                       (2,1,0), (2,1,1), (2,1,2),
                       (2,2,0), (2,2,1), (2,2,2),
                     ]
    results = [ [(2,0), ()],
                [(2,1), (0,), (1,)],
                [(2,2), (0,0), (0,1), (1,0), (1,1)],
                [(2,3), (0,0,0), (0,0,1), (0,1,0), (0,1,1),
                        (1,0,0), (1,0,1), (1,1,0), (1,1,1), ],
                [(3,2), (0,0), (0,1), (0,2), (1,0), (1,1), (1,2),
                        (2,0), (2,1), (2,2) ],
              ]
    for r in results:
        n,k = r[0]
        r = r[1:]
        routine_result = list(iter_count_in_base(n,k))
        assert routine_result == r, (n,k,routine_result)

class permutations(object):
    """Iterator for the permutations of a sequence.

    Example:

    >>> list(permutations(3))
    [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]
    >>> list(permutations(["a", "b", "c"]))
    [('a', 'b', 'c'),
     ('a', 'c', 'b'),
     ('b', 'a', 'c'),
     ('b', 'c', 'a'),
     ('c', 'a', 'b'),
     ('c', 'b', 'a')]
    """
    def __init__(self, objs):
        """Create an iterator over the permutations of the sequence objs.
        objs may be an integer, in which case range(objs) is used.
        """
        object.__init__(self)
        try:
            n = len(objs)
        except:
            n = int(objs)
            objs = range(0, n)
        self.objs = objs

    def __iter__(self):
        objs = self.objs
        n = len(objs)
        if n == 0:
            return iter([()])
        return _count.PermutationIterator(objs)

    def __len__(self):
        return int(factorial(len(self.objs)))

def _test_permutations():
    pi = permutations( (0,) )
    assert list(pi) == [ (0,) ]
    pi = permutations(2)
    assert list(pi) == [ (0,1), (1,0) ]
    pi = permutations(3)
    assert len(pi) == 6
    assert list(pi) == [ (0,1,2), (0,2,1), (1,0,2), (1,2,0), (2,0,1), (2,1,0) ]
    pi = permutations("abc")
    assert len(pi) == 6
    assert list(pi) == [ ('a','b','c'), ('a','c','b'),
                         ('b','a','c'), ('b','c','a'),
                         ('c','a','b'), ('c','b','a') ]

# seed with factorials to 20
_factorial_cache = [1,
                    1,
                    2,
                    6,
                    24,
                    120,
                    720,
                    5040,
                    40320,
                    362880,
                    3628800,
                    39916800,
                    479001600,
                    6227020800,
                    87178291200,
                    1307674368000,
                    20922789888000,
                    355687428096000,
                    6402373705728000,
                    121645100408832000,
                    2432902008176640000]

def factorial(N):
    """Return N!

    This caches results, so subsequent calls will be O(1).
    """
    if N < 0:
        return 0
    factorials = _factorial_cache
    n = len(factorials)
    if N >= n:
        f_i = factorials[-1]
        for i in range(n, N+1):
            f_i = i * f_i
            factorials.append(f_i)
    return factorials[N]
factorial = bindconstants.make_constants()(factorial)

def _test_factorial():
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(2) == 2
    assert factorial(3) == 6
    assert factorial(4) == 24
    assert factorial(5) == 120
    assert factorial(4) == 24
    assert factorial(3) == 6
    assert factorial(2) == 2
    assert factorial(1) == 1
    assert factorial(0) == 1
    assert factorial(20) == 2432902008176640000
    assert factorial(21) == 51090942171709440000L
    assert factorial(40) == 815915283247897734345611269596115894272000000000L
    assert factorial(40) == 815915283247897734345611269596115894272000000000L

def binomial(n, k):
    """Return the binomial coefficient nCk = n!/(k!*(n-k)!)"""
    if k < 0 or n < 0 or k > n:
        return 0
    return factorial(n) / (factorial(k) * factorial(n-k))

def _test_binomial():
    assert binomial(0,0) == 1
    assert binomial(1,0) == 1
    assert binomial(1,1) == 1
    assert binomial(4,2) == 6
    assert binomial(33, 20) == 573166440

def multinomial(divisions):
    """Return the multinomial n!/(n1!*n2!*...*nk!) where n1+n2+...+nk = n.
    """
    n = sum(divisions)
    r = 1
    for k in divisions:
        r *= factorial(k)
    # this is exact
    return factorial(n) / r
multinomial = bindconstants.make_constants()(multinomial)

def _test_multinomial():
    assert multinomial((5,)) == 1
    assert multinomial((2,3)) == binomial(5, 2)
    assert multinomial((1,1,1,1,1)) == factorial(5)

def count_repeats(lst):
    counts = {}
    cg = counts.get
    for e in lst:
        counts[e] = cg(e,0) + 1
    return counts

# We have some optimized routines for small values
count_permutations2 = _count.count_permutations2
count_permutations3 = _count.count_permutations3
count_permutations4 = _count.count_permutations4

def count_permutations(lst):
    """Determine number of permutations of elements of lst, taking into
    account elements which are the same.

    If there are n1 elements of type a, n2 of type b, and n3 of type c,
    the number of permutation is the multinomial n! / (n1!*n2!*n3!)
    where n1+n2+n3 = n.
    """
    l = len(lst)
    if l == 0:
        return 1
    elif l == 1:
        return 1
    elif l == 2:
        # inlined for speed
        if lst[0] == lst[1]:
            return 1
        else:
            return 2
    elif l == 3:
        # inlined for speed
        l0, l1, l2 = lst
        if l0 == l1:
            if l1 == l2:
                return 1
            else:
                return 3
        else:
            if l1 == l2:
                return 3
            elif l0 == l2:
                return 1
            else:
                return 6
    elif l == 4:
        return count_permutations4(*lst)
    counts = {}
    cg = counts.get
    for e in lst:
        counts[e] = cg(e,0) + 1
    return multinomial(counts.values())
count_permutations = bindconstants.make_constants()(count_permutations)

def _test_count_permutations():
    assert count_permutations(()) == 1
    assert count_permutations((1,)) == 1
    assert count_permutations((1,1)) == 1
    assert count_permutations((1,2)) == 2
    assert count_permutations((1,2,3)) == 6
    assert count_permutations((1,1,1)) == 1
    assert count_permutations((1,1,2)) == 3
    assert count_permutations((1,1,'a')) == 3

    p4 = { 1 : ["aaaa"],
           4 : ["aaab", "aaba", "abaa", "baaa"],
           6 : ["aabb", "abab", "abba"],
           12 : ["aabc", "abac", "abca", "baac", "baca", "bcaa"],
           24 : ["abcd"] }
    for n in p4:
        for s in p4[n]:
            assert count_permutations(s) == n, (s, n)

def sort2(a, b):
    if a > b:
        return b, a
    return a, b

def sort3(s0, s1, s2):
    if s0 > s2:
        s0, s2 = s2, s0
    if s0 > s1:
        s0, s1 = s1, s0
    if s1 > s2:
        s1, s2 = s2, s1
    return s0, s1, s2

def sort4(s0, s1, s2, s3):
    # found this algorithm by genetic programming
    if s1 > s3:
        s1, s3 = s3, s1
    if s0 > s2:
        s0, s2 = s2, s0
    if s2 > s3:
        s2, s3 = s3, s2
    if s0 > s1:
        s0, s1 = s1, s0
    if s1 > s2:
        s1, s2 = s2, s1
    return s0, s1, s2, s3

sort2_int = _count.sort2_int
sort3_int = _count.sort3_int
sort4_int = _count.sort4_int

def _test_sort2():
    for a, b in [(0,1), (1,0)]:
        assert sort2(a,b) == (0,1)

def _test_sort2_int():
    for a, b in [(0,1), (1,0)]:
        assert sort2_int(a,b) == (0,1)

def _test_sort3():
    for a, b, c in [(0,1,2), (0,2,1), (1,0,2), (1,2,0), (2,0,1), (2,1,0)]:
        t = sort3(a, b, c)
        assert t == (0,1,2), "sort3"

def _test_sort3_int():
    for a, b, c in [(0,1,2), (0,2,1), (1,0,2), (1,2,0), (2,0,1), (2,1,0)]:
        t = sort3_int(a, b, c)
        assert t == (0,1,2), "sort3_int"

def _test_sort4():
    for a, b, c, d in permutations(4):
        t = sort4(a, b, c, d)
        assert t == (0, 1, 2, 3), "sort4"

def _test_sort4_int():
    for a, b, c, d in permutations(4):
        t = sort4_int(a, b, c, d)
        assert t == (0, 1, 2, 3), "sort4_int"

if __name__ == '__main__':
    import pydmc.simpletest
    pydmc.simpletest.main()
