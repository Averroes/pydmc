"""
Helper module for pydmc.count.
"""
# References:
#   [NW] Nijenhuis & Wilf, "Combinatorial Algorithms: For Computers and
#      Calculators". Academic Press: 1978, 2nd ed.
#   [KS] Kreher & Stinson, "Combinatorial Algorithms: Generation, Enumeration,
#      and Search". CRC Press: 1999.

cdef extern from "Python.h":
    ctypedef struct PyObject:
        pass
    void *PyMem_Malloc(int n)
    void PyMem_Free(void *p)
    int PySequence_Length(object o)
    object PySequence_Tuple(object o)
    int PyTuple_Check(object o)
    object PyTuple_New(int len)
    void PyTuple_SET_ITEM(object p, int pos, PyObject *o)
    PyObject *PyTuple_GetItem(object p, int pos)
    void Py_INCREF(PyObject *o)
    void Py_XDECREF(object o)

    int PyDict_Size(object o)

cdef class _IntArray:
    cdef unsigned int length
    cdef int *data

    def __init__(self, unsigned int length):
        self.length = length
        self.data = <int *>PyMem_Malloc(self.length * sizeof(int))

    def __dealloc__(self):
        PyMem_Free(self.data)
        self.data = NULL

    def __str__(self):
        s = ['<_IntArray %d:' % (self.length)]
        cdef int i
        for i from 0 <= i < self.length:
            s.append('%d' % i)
        return ' '.join(s) + '>'

    cdef map_to_tuple(self, objs):
        cdef object t "t"
        cdef PyObject *o "o"
        cdef unsigned int i "i"
        cdef int n
        if not PyTuple_Check(objs):
            raise TypeError, "must use a tuple"
        t = PyTuple_New(self.length)
        for i from 0 <= i < self.length:
            n = self.data[i]
            o = PyTuple_GetItem(objs, n)
            if o == NULL:
                raise IndexError, "tuple index out of range"
            # need to incref as PyTuple_SET_ITEM steals a reference to o, but
            # Pyrex acts as if it borrows one.
            Py_INCREF(o)
            PyTuple_SET_ITEM(t, i, o)
        return t

cdef _IntArray to_intarray(sequence):
    cdef _IntArray ia
    ia = _IntArray(len(sequence))
    cdef int i
    for i from 0 <= i < ia.length:
        ia.data[i] = sequence[i]
    return ia

#
# [NW] and [KS] will help, but the algorithm below is mine.
#
# For a fixed k, we could code this in Python as
# for t[0] in range(0, limits[0]):
#     for t[1] in range(w[1]*t[index_map[1]] + inc[i], limits[1]):
#         for t[2] in range(w[2]*t[index_map[2]] + inc[i], limits[2]):
#             ...
#                 yield tuple(t)
#
# then counting is done using
#   limits[i] = n
#   w[i] = 0
#   index_map[i] = irrelevant
#   inc[i] = 0
#   (note that multi-base counts are easily done with different limits)
# k-multisets (symmetric indices) are generated with
#   limits[i] = n
#   w[i] = 1
#   index_map[i] = i-1
#   inc[i] = 0
# and k-subsets (symmetric indices with no repeats) with
#   limits[i] = n-k+i+1
#   w[i] = 1
#   index_map[i] = i-1
#   inc[i] = 1
#
# With this framework, we can also do more complicated symmetries. For
# instance, to generate indices for which the first and fourth are swappable,
# and the second and third, we can do
#   limits = [n,n,n,n]
#   w = [0,0,1,1]
#   index_map = [-1,-1,1,0]
#   inc = [0,0,0,0]
# (note that we use index_map[i] == -1 for when w[i] == 0; in the code, we'll
# drop w, and use index_map only)

cdef class LexicographicIterator:
    cdef readonly unsigned int k "k"
    cdef int generator_state
    cdef objs
    cdef _IntArray T, limits, index_map, increments

    def __init__(self, objs, limits, index_map, increments):
        cdef int i, im
        self.limits = to_intarray(limits)
        self.k = self.limits.length
        for i from 0 <= i < self.k:
            self.limits.data[i] = self.limits.data[i] - 1
        self.index_map = _IntArray(self.k)
        for i from 0 <= i < self.k:
            im = index_map[i]
            if im < 0:
                self.index_map.data[i] = -1
            elif im > self.k:
                raise ValueError, "index map %d is out of range" % im
            else:
                self.index_map.data[i] = im
        self.increments = to_intarray(increments)
        self.objs = PySequence_Tuple(objs)
        self.T = _IntArray(self.k)
        self.T.data[0] = 0
        self.rollover_next(0)
        self.generator_state = 0

    cdef rollover_next(self, int g):
        cdef int i, im, *T, *index_map, *increments
        T = self.T.data
        index_map = self.index_map.data
        increments = self.increments.data
        for i from g+1 <= i < self.k:
            im = index_map[i]
            if im < 0:
                T[i] = 0
            else:
                T[i] = T[im] + increments[i]

    cdef _current(self):
        return self.T.map_to_tuple(self.objs)
    def current(self):
        return self._current()

    def __iter__(self):
        return self

    # As a generator, you'd do something like
    # <init>
    # while 1:
    #     yield T
    #     self._next()
    #     if self.finished:
    #         break
    #
    # which we transform to:
    #
    # yield T
    # while 1:
    #     self._next()
    #     if self.finished:
    #         break
    #     yield T
    #
    # then we can code that as an iterator with state-changes keeping
    # track of which yield we're being called after.
    # (I wish Pyrex supported yield)

    cdef void _next(self):
        cdef int *T, *limits
        T = self.T.data
        limits = self.limits.data
        cdef int g
        for g from self.k > g >= 0:
            if T[g] < limits[g]:
                break
        else:
            self.generator_state = 2
            return
        T[g] = T[g] + 1
        self.rollover_next(g)

    def __next__(self):
        if self.generator_state == 0:
            # first time in loop
            self.generator_state = 1
            return self._current()
        elif self.generator_state == 2:
            raise StopIteration
        self._next()
        if self.generator_state == 2:
            raise StopIteration()
        return self._current()

# This is taken from Algorithm 2.14 in [KS]. Modified to use 0-based indexing.

cdef class PermutationIterator:
    cdef objs
    cdef _IntArray perm
    cdef int generator_state

    def __init__(self, objs):
        cdef int i, n
        self.objs = PySequence_Tuple(objs)
        n = len(self.objs)
        self.perm = _IntArray(n)
        for i from 0 <= i < n:
            self.perm.data[i] = i
        self.generator_state = 0

    cdef _current(self):
        return self.perm.map_to_tuple(self.objs)
    def current(self):
        return self._current()

    cdef void _next(self):
        cdef int n "n", i "i", j "j", pi "pi"
        cdef int *perm
        n = self.perm.length
        perm = self.perm.data
        # 1.
        # Find i such that perm[i] < perm[i+1] > perm[i+2] > ... > perm[n-1]
        # We terminate if none is found.
        for i from n-1 > i >= 0:
            if perm[i+1] >= perm[i]:
                break
        else:
            self.generator_state = 2
            return
        # 2.
        # Find j such that perm[j] > perm[i]
        #     and perm[k] < perm[i] for j < k < n
        #  --> j is the last element in perm[i+1:] that is greater than perm[i]
        pi = perm[i]
        for j from n > j >= 0:
            if perm[j] >= pi:
                break
        # 3.
        # Interchange perm[i] and perm[j]
        perm[i] = perm[j]
        perm[j] = pi
        # 4.
        # Reverse the sublist perm[i+1:]
        # perm[i+1] <-> perm[n-1]
        # perm[i+2] <-> perm[n-2]
        # etc.
        cdef unsigned int k "k" , kc "kc"
        for k from i+1 <= k < n:
            kc = n - k + i
            if k >= kc:
                break
            pi = perm[k]
            perm[k] = perm[kc]
            perm[kc] = pi

    def __next__(self):
        if self.generator_state == 0:
            # first time in loop
            if self.perm.length == 1:
                # n=1 is a trivial case, and not handled by the above algorithm
                self.generator_state = 2
            else:
                self.generator_state = 1
            return self._current()
        elif self.generator_state == 2:
            raise StopIteration
        self._next()
        if self.generator_state == 2:
            raise StopIteration
        return self._current()

# For speed, we implement some of the counting permutations here
def count_permutations2(l0, l1):
    """
    count_permutations3(a, b)

    Count the number of possible permutations of a and b.
    """
    if l0 == l1:
        return 1
    else:
        return 2

def count_permutations3(l0, l1, l2):
    """
    count_permutations3(a, b, c)

    Count the number of possible permutations of a, b, and c.
    """
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

def count_permutations4(l0, l1, l2, l3):
    """
    count_permutations4(a, b, c, d)

    Count the number of possible permutations of a, b, c, and d.
    """
    # doing something similiar to count_permutations3, using comparisions,
    # would probably be faster.
    # It's also *much* messier.
    # This is pretty fast, though.
    cdef int lc
    counts = {l0 : 0, l1 : 0, l2 : 0, l3 : 0}
    counts[l0] = counts[l0] + 1
    counts[l1] = counts[l1] + 1
    counts[l2] = counts[l2] + 1
    counts[l3] = counts[l3] + 1
    lc = PyDict_Size(counts)
    if lc == 1:
        # aaaa
        return 1
    elif lc == 2:
        # distinguish between aaab and aabb
        if counts[l0] == 2:
            # aabb
            return 6
        else:
            # aaab
            return 4
    elif lc == 3:
        # aabc
        return 12
    else:
        # abcd
        return 24

# Specialized sorting routines of integers. Useful when generating
# indices for a symmetric symbol.

def sort2_int(int a, int b):
    if a > b:
        return b, a
    return a, b

def sort3_int(int s0, int s1, int s2):
    if s0 > s2:
        s0, s2 = s2, s0
        if s1 > s2:
            s1, s2, = s2, s1
    elif s0 > s1:
        s0, s1 = s1, s0
    return s0, s1, s2

def sort4_int(int i0, int i1, int i2, int i3):
    cdef int s0, s1, s2, s3
    # found this algorithm by genetic programming
    if i1 > i3:
        s1, s3 = i3, i1
    else:
        s1, s3 = i1, i3
    if i0 > i2:
        s0, s2 = i2, i0
    else:
        s0, s2 = i0, i2
    if s2 > s3:
        s2, s3 = s3, s2
    if s0 > s1:
        s0, s1 = s1, s0
    if s1 > s2:
        s1, s2 = s2, s1
    return s0, s1, s2, s3
