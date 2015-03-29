This is a collection of Python routines that I've written.

Included:

`pydmc.count`: fast routines for iterating and counting permutations, combinations, subsets, and multisets. Also compute factorials, binomials, and multinomials.

`pydmc.datafile`: support for lightly-structured data files of numbers, appropriate for reading in xmgrace or other tools, but including some metadata.

`pydmc.simpletest`: a simple unit test library. Add functions beginning with `_test` to your module, and call `pydmc.simpletest.test_all(module)`