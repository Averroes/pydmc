"""
From: David Eppstein <eppstein@ics.uci.edu>
Subject: Re: nearest neighbor in 2D
Newsgroups: comp.lang.python
Date: Mon, 03 Nov 2003 17:11:45 -0800
Organization: Information and Computer Science, UC Irvine

> >I have a list of two tuples containing x and y coord
> >  
> > (x0, y0)
> > (x1, y1)
> > ...
> > (xn, yn)
> >
> >Given a new point x,y, I would like to find the point in the list
> >closest to x,y.  I have to do this a lot, in an inner loop, and then I
> >add each new point x,y to the list.  I know the range of x and y in
> >advance.  

Here's some not-very-heavily-tested code for doing this using a kD-tree. 

Worst case efficiency is still linear per point or quadratic total 
(unlike some other more sophisticated data structures) but in practice 
if your points are reasonably well behaved this should be pretty good; 
e.g. I tried it with 10000 random points (each queried then added) and 
it made only 302144 recursive calls to nearestNeighbor.

Also note that only the test code at the end restricts to two 
dimensions, everything else works in arbitrary numbers of dimensions.
"""
import Numeric as Num

def dist2(p,q):
    """Squared distance between p and q."""
    d = sum([ (p[i]-q[i])**2 for i in range(len(p)) ])
    return d

class kdtree:
    def __init__(self,dim=2,index=0):
        self.dim = dim
        self.index = index
        self.split = None

    def addPoint(self,p):
        """Include another point in the kD-tree."""
        if self.split is None:
            self.split = p
            self.left = kdtree(self.dim, (self.index + 1) % self.dim)
            self.right = kdtree(self.dim, (self.index + 1) % self.dim)
        elif self.split[self.index] < p[self.index]:
            self.left.addPoint(p)
        else:
            self.right.addPoint(p)

    def nearestNeighbor(self,q,maxdist2):
        """Find pair (d,p) where p is nearest neighbor and d is squared
        distance to p. Returned distance must be within maxdist2; if
        not, no point itself is returned.
        """
        solution = (maxdist2+1,None)
        def nmin(a, b):
            if a[1] is None:
                return b
            return min(a, b)
        if self.split is not None:
            d = dist2(self.split, q)
            solution = nmin(solution, (d, self.split))
            d2split = (self.split[self.index] - q[self.index])**2
            if self.split[self.index] < p[self.index]:
                r = self.left.nearestNeighbor(q,solution[0])
                solution = nmin(solution, r)
                if d2split < solution[0]:
                    r = self.right.nearestNeighbor(q,solution[0])
                    solution = nmin(solution, r)
            else:
                r = self.right.nearestNeighbor(q, solution[0])
                solution = nmin(solution, r)
                if d2split < solution[0]:
                    r = self.left.nearestNeighbor(q, solution[0])
                    solution = nmin(solution, r)
        return solution

def test_kdtree(points):
    max_dist2 = max_x**2 + max_y**2
    k = kdtree()
    for p in points:
        k.addPoint(p)

    for i in range(0.1*len(points)):
        d, q = k.nearestNeighbor(p, max_dist2)

if __name__ == "__main__":
    import math
    import random
    
    n_points = 5000
    max_x = 1000
    max_y = 1000
    max_dist2 = max_x**2 + max_y**2
    
    k = kdtree()
    for i in range(n_points):
        x = round(max_x*random.random())
        y = round(max_y*random.random())
        p = Num.array( (x,y) )
        
        if i == 0:
            pass
#            print 'new point',p
        else:
            d,q = k.nearestNeighbor(p,max_dist2)
#            print 'new point', p, 'has neighbor',
#            print q, 'at distance', math.sqrt(d)

        k.addPoint(p)
