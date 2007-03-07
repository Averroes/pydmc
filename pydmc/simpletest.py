import sys
import warnings
import pdb
import traceback
import types
import inspect
import time

from pydmc.util import is_string, has_length, colourise

class TestError(Exception):
    pass

def assert_raises(exc, func, *args, **kw):
    """Check that func(*args, **kw) raises exc"""
    try:
        func(*args, **kw)
    except exc:
        pass
    else:
        raise TestError('did not raise %r' % exc)

class FloatingPointError(Exception):
    pass

class FloatingPointWarning(Warning):
    pass

def get_array_package():
    try:
        import numpy
        return numpy
    except ImportError:
        try:
            import numarray
            return numarray
        except ImportError:
            import Numeric
            return Numeric
    return None

def _get_abs_diff(a, b):
    NX = get_array_package()
    flat_a = NX.ravel(a)
    flat_b = NX.ravel(b)
    flat_d = NX.absolute(flat_a - flat_b)
    return NX.maximum.reduce(flat_d)

def assert_fp(a, b, atol=1e-12, warn=100, info=None):
    """Assert that a and b are withing atol of each other.

    If a and b differ by more than warn*atol, raise FloatingPointError,
    else just emit a warning.
    """
    seq_a = has_length(a)
    seq_b = has_length(b)
    if (seq_a and not seq_b) or (not seq_a and seq_b):
        raise ValueError(
            "trying to compare a sequence and non-sequence: a=%r b=%r" %
            (a,b))
    NX = get_array_package()
    aa = NX.asarray(a)
    ab = NX.asarray(b)
    if aa.shape != ab.shape:
        raise ValueError("sequences have different shapes:\na%s=%r\nb%s=%r" %
                         (aa.shape, a, ab.shape, b))
    d = _get_abs_diff(a, b)
    if d > atol:
        if seq_a:
            as_info = '\na=%r\nb=%r\n|a-b|=%.4g' % (a, b, d)
        else:
            as_info = 'a=%r b=%r |a-b|=%.4g' % (a, b, d)
        if info is not None:
            as_info += ' ' + str(info)
        if d > warn*atol:
            raise FloatingPointError(as_info)
        else:
            warnings.warn(as_info, FloatingPointWarning, stacklevel=2)

def assert_equal(a, b, info=None):
    """Assert that a and b are equal elementwise.

    Use this if you're trying to compare arrays for equality, as
    a == b won't give what you want in that case.
    """
    assert_fp(a, b, atol=0, warn=0, info=info)

def fail_on_fp():
    """Convert FloatingPointWarning (as set by assert_fp) to errors."""
    warnings.filterwarnings("error", category=FloatingPointWarning)

def _get_lineno(func):
    try:
        lines, lnum = inspect.getsourcelines(func)
    except IOError:
        lnum = 0
    return lnum

def sort_tests(name_func_pairs):
    decorated = [ (_get_lineno(func), name, func)
                  for name, func in name_func_pairs ]
    decorated.sort()
    return [ (name, func) for lineno, name, func in decorated ]

def filter_tests(name_func_pairs, test_prefix='_test'):
    if is_string(test_prefix):
        test_prefix = [test_prefix]
    tests = []
    for name, func in name_func_pairs:
        for tp in test_prefix:
            if name.startswith(tp):
                tests.append( (name,func) )
                break
    return sort_tests(tests)

def import_module(name):
    mod = __import__(name)
    components = name.split('.')
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod

def test_suite_from_module(module_name, test_prefix, module=None):
    if module is None:
        module = import_module(module_name)
    tests = filter_tests(inspect.getmembers(module, inspect.isfunction),
                         test_prefix)
    tests = [ ('%s.%s' % (module_name, name), f) for name, f in tests ]
    return tests

def test_suite(suite, test_prefix='_test'):
    # tests is a list of (name, function) pairs
    if suite is None:
        suite = '__main__'
    if is_string(suite):
        tests = test_suite_from_module(suite, test_prefix)
    elif type(suite) is types.FunctionType:
        # function
        tests = filter_tests([(suite.__name__, suite)], test_prefix)
    elif hasattr(suite, "__dict__"):
        # module or class
        tests = filter_tests(suite.__dict__.items(), test_prefix)
    elif hasattr(suite, 'items'):
        # it's a dictionary-like thing
        tests = filter_tests(suite.items(), test_prefix)
    elif has_length(suite):
        # sequency-thingy: assuming it's got (name, function) pairs
        if len(suite) == 2 and is_string(suite[0]) and callable(suite[1]):
            # a (name, function) pair
            tests = [suite]
        else:
            # recurse
            tests = []
            for s in suite:
                tests.extend( test_suite(s, test_prefix) )
    else:
        # complain
        raise ValueError("don't know how to handle the passed suite")
    return tests

def _print_exception(caller):
    """Print the current exception traceback, chopping off the top references
    to this module.
    """
    try:
        etype, value, tb = sys.exc_info()
        this_file = inspect.getsourcefile(caller)
        pp_tb = traceback.extract_tb(tb)
        limit = None
        for i, (filename, lineno, fname, text) in enumerate(pp_tb):
            if filename == this_file:
                pp_tb = pp_tb[i+1:]
                break
        tb_text = ''.join(traceback.format_list(pp_tb))
        lines = traceback.format_exception_only(etype, value)
        tb_text += ' '.join(lines)
        tb_text = '  ' + tb_text[:-1].replace('\n', '\n  ') + tb_text[-1]
        sys.stderr.write(tb_text)
    finally:
        etype = value = tb = None

def test_all(tests=None, verbose=False, quiet=False,
             debugger=False, test_prefix='_test'):
    def output(msg, eol=True):
        if not quiet:
            if eol:
                print msg
            else:
                print msg,
    tests = test_suite(tests, test_prefix)
    ntests = 0
    failures = 0
    if len(tests) == 0:
        output('No tests found with prefix %r!' % (test_prefix,))
        return 0
    bt = time.clock()
    for name, test in tests:
        ntests += 1
        if verbose:
            output('testing %s ...'%(name,), eol=False)
        passed = True
        try:
            test()
        except:
            passed = False
            if verbose:
                output('failed')
            output('Exception in %s'%(colourise(name, 'error'),))
            _print_exception(test_all)
            failures += 1
            if debugger:
                pdb.post_mortem(sys.exc_info()[2])
        if passed and verbose:
            output('passed')
    elapsed = time.clock() - bt

    if failures == 0:
        output("%d tests in %.3f s" % (ntests, elapsed))
    else:
        output("%d tests in %.3f s; %d failures" % (ntests, elapsed, failures))
    return failures

def main(tests=None, verbose=False, debugger=False, test_prefix='_test'):
    import optparse
    parser = optparse.OptionParser('usage: %prog [options]',
                description='Unit tests for this module\n')
    parser.add_option('-v', '--verbose', dest='verbose',
                      action='store_true', default=verbose,
                      help='be verbose')
    parser.add_option('-e', '--errors', dest='errors',
                      action='store_true', default=False,
                      help="turn (test module defined) warnings into errors")
    parser.add_option('-d', '--debugger', dest='debugger',
                      action='store_true', default=False,
                      help="enter debugger on test errors")
    options, args = parser.parse_args()
    if len(args) != 0:
        parser.error('too many args')
    if options.errors:
        fail_on_fp()
    test_all(tests, verbose=options.verbose, debugger=options.debugger,
             test_prefix=test_prefix)

#
# Unit tests for a unit tester :-)
#

def _test_raises():
    def div(a, b):
        return a / b
    assert_raises(ZeroDivisionError, div, 1, 0)
    try:
        assert_raises(ZeroDivisionError, div, 1, 1)
    except TestError:
        pass
    else:
        assert 0

def _test_fp1():
    filters = warnings.filters[:]
    fail_on_fp()
    try:
        assert_raises(FloatingPointError, assert_fp, 1.0, 0.1, atol=1e-12)
        assert_raises(FloatingPointWarning, assert_fp, 1.0, 1.0+2e-12,
                      atol=1e-12, warn=10)
        assert_fp(1.0, 1.0+1e-10, atol=1e-5)
        assert_fp(0.0, 1e-10, atol=1e-5)
    finally:
        warnings.filters[:] = filters

def _test_fp2():
    import Numeric
    a = Numeric.array([[1., 2., 3.], [4., 5., 6.]])
    b = Numeric.array([[1., 2., 3.], [4., 5+1e-14, 6.]])
    assert_raises(FloatingPointError, assert_fp, a, b, atol=1e-12)
    b = [[1., 2., 3.], [4., 5+1e-14, 6.]]
    assert_raises(FloatingPointError, assert_fp, a, b, atol=1e-12)

# example
def _test_ex():
    s = 0
    for i in range(1, 100+1):
        s += i
    assert s == 5050

if __name__ == '__main__':
    main()
