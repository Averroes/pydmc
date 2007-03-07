__all__ = ['diff1d']

#from Numeric import *

def diff1d(y, h):
    """Numerically differentiate a 1D array y, with regular spacing h."""
    dy = y.copy()
    dy[1:] -= y[:-1]
    dy /= h
    dy[0] = (y[1]-y[0])/h
    return dy

if __name__ == '__main__':
    import pydmc.simpletest
    pydmc.simpletest.main()
