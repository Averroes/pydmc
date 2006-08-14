def is_sequence(s):
    try:
        iter(s)
    except TypeError:
        return False
    return True

def plot(*lines, **kw):
    import biggles
    dots = kw.get('dots', 0)
    colours = ['black', 'blue', 'red', 'green', 'orange', 'purple']

    plot = biggles.FramedPlot()

    for i in range(0, len(lines)):
        data = lines[i]
        if not is_sequence(data):
            raise TypeError('not a sequence')
        if len(data) == 2 and is_sequence(data[0]) and is_sequence(data[1]):
            x = data[0]
            y = data[1]
        elif not is_sequence(data[0]):
            x = range(0, len(data))
            y = data
        else:
            x = [ d[0] for d in data ]
            y = [ d[1] for d in data ]
        color = colours[ i % len(colours) ]
        if dots:
            l = biggles.Points(x, y, color=color)
        else:
            l = biggles.Curve(x, y, color=color)
        plot.add(l)
    plot.show()
    return plot

if __name__ == '__main__':
    import math
    di = 5.*math.pi/5.
    data = []
    for i in range(18):
        data.append((float(i)*di,
                     (math.sin(float(i)*di)-math.cos(float(i)*di))))

    plot(data)
