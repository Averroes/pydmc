#! /usr/bin/env python

import re
from copy import copy

attributes_pat = re.compile('#\s*([a-zA-Z_][a-zA-Z_0-9]*):\s*(.*)$')

def filename_to_fo(filename, mode='r'):
    if type(filename) == type(""):
        return open(filename, mode)
    else:
        return filename

class XMLWriter(object):
    def __init__(self, fp, indent=1):
        self.fp = filename_to_fo(fp, 'w')
        self.indent = indent
        self._tag_stack = []
        self._need_indent = 0

    def close(self):
        self.fp.close()

    def toplevel(self):
        self.fp.write('<?xml version="1.0"?>\n')

    def _eol(self):
        self.fp.write('\n')
        self._need_indent = 1

    def _write(self, *text):
        if self.indent > 0 and self._need_indent:
            self.fp.write(' '*self.indent*len(self._tag_stack))
            self._need_indent = 0
        for t in text:
            self.fp.write(t)

    def tag(self, name, _noeol=0, _isempty=0, **kw):
        tag = ['<', name]
        for k, v in kw.items():
            tag.append(' %s="%s"'%(k, v))
        if _isempty:
            tag.append('/>')
        else:
            tag.append('>')
        self._write(*tag)
        if not _isempty:
            self._tag_stack.append(name)
        if not _noeol:
            self._eol()

    def endtag(self, should_be=None):
        name = self._tag_stack.pop()
        if should_be and name != should_be:
            raise ValueError, 'wrong tag; got %s, expected %s'%(should_be,name)
        self._write('</', name, '>')
        self._eol()

    def textline(self, text):
        self._write(text)
        self._eol()

    def text(self, text):
        self._write(text)

    def node(self, name, contents, **kw):
        self.tag(name, _noeol=1, **kw)
        self._write(contents)
        self.endtag()

    def empty(self, name, **kw):
        self.tag(name, _isempty=1, **kw)

class Data(object):
    def __init__(self, data=[]):
        self.data = data[:]
        self.ncols = None
    def append_dataline(self, d):
        if self.ncols is None:
            self.ncols = len(d)
        if len(d) != self.ncols:
            raise ValueError, \
                'data tuple is wrong size; got %d, expected %d'%(
                    len(d), self.ncols)
        self.data.append(d)

    def col(self, n):
        return [ d[n] for d in self.data ]

    def __getitem__(self, i):
        return self.data[i]
    def __len__(self):
        return len(self.data)

    def row(self, n):
        return self.data[n]

    def sort(self, on_col=0):
        if on_col == 0:
            self.data.sort()
        else:
            data = [ (d[on_col], d) for d in self.data ]
            data.sort()
            self.data = data

    def xy(self, xcol=0, ycol=1):
        new_data = XYData()
        new_data.data = [ (d[xcol], d[ycol]) for d in self.data ]
        return new_data

    def write_xml(self, xml):
        xml.tag('data', columns=self.ncols)
        for d in self.data:
            fmttd = [ repr(x) for x in d ]
            xml.textline(' '.join(fmttd))
        xml.endtag('data')

class XYData(Data):
    def __init__(self, data=[]):
        Data.__init__(self, data)
        self.ncols = 2

    def append(self, x, y):
        self.append_dataline( (x, y) )

    def x(self, n=None):
        if n is None:
            return [ d[0] for d in self.data ]
        else:
            return self.data[n][0]
    def y(self, n=None):
        if n is None:
            return [ d[1] for d in self.data ]
        else:
            return self.data[n][1]

    def write_xml(self, xml):
        xml.tag('xydata')
        for d in self.data:
            xml.textline('%s %s'%(repr(d[0]), repr(d[1])))
        xml.endtag('xydata')

class Style(object):
    type = 'style'
    def __init__(self, *args, **attrs):
        attributes = {}
        if len(args) == 1 and hasattr(args[0], 'attributes'):
            attributes.update(args[0].attributes)
        attributes.update(attrs)
        self.__dict__['attributes'] = attributes

    def __repr__(self):
        l = [ '%s=%r'%(k, self.attributes[k]) for k in self.attributes ]
        return '<Style ' + ' '.join(l) + '>'

    def __getattr__(self, name):
        try:
            return self.__dict__['attributes'][name]
        except KeyError:
            raise AttributeError
    def __setattr__(self, name, value):
        if name in self.__dict__:
            self.__dict__[name] = value
        else:
            self.attributes[name] = value
    def __delattr__(self, name):
        del self.attributes[name]

    def get(self, name, default=None):
        return self.attributes.get(name, default)

    def write_xml(self, xml):
        xml.tag(self.type)
        for k, v in self.attributes.items():
            xml.node(k, str(v))
        xml.endtag(self.type)

default_style = Style(colour='black', bw_linetype='solid')

_Curve_ID_n = 0
class Curve(object):
    type = 'curve'
    def __init__(self, xydata, style=None, legend=''):
        global _Curve_ID_n
        self._id = 'curve%d'%_Curve_ID_n
        _Curve_ID_n += 1
        self.legend = legend
        self.xydata = xydata
        if style is None:
            style = copy(default_style)
        self.style = style

    def write_xml(self, xml):
        xml.tag(self.type, id=self._id)
        xml.node('legend', self.legend)
        self.style.write_xml(xml)
        self.xydata.write_xml(xml)
        xml.endtag(self.type)

def read_data(file):
    fo = filename_to_fo(file, 'r')
    attributes = {}
    data = Data()
    for line in fo.xreadlines():
        m = attributes_pat.match(line)
        if m:
            attributes[m.group(1)] = m.group(2)
        elif not line.startswith('#'):
            d = map(float, line.strip().split())
            data.append_dataline(d)
    return data, attributes

class TextStyle(Style):
    type = 'textstyle'

default_textstyle = TextStyle(face='serif',
                              size=4, valign='center', halign='center')
class DataLabel(object):
    type = 'label'
    def __init__(self, x, y, label, style=None):
        self.x = float(x)
        self.y = float(y)
        self.text = label
        self.style = style or copy(default_textstyle)

    def write_xml(self, xml):
        xml.tag(self.type)
        self.style.write_xml(xml)
        xml.empty('position', x=self.x, y=self.y)
        xml.node('text', self.text)
        xml.endtag(self.type)

def read_labels(file):
    fo = filename_to_fo(file, 'r')
    attributes = {}
    labels = []
    for line in fo.xreadlines():
        line = line.strip()
        m = attributes_pat.match(line)
        if m:
            attributes[m.group(1)] = m.group(2)
        elif not line.startswith('#'):
            sx, sy, text = line.split(None, 2)
            tstyle = TextStyle(**attributes)
            labels.append(DataLabel(float(sx), float(sy), text,
                                    style=tstyle))
    return labels

default_legboxstyle = TextStyle(face='serif', size=1, halign='left')
class LegendBox(object):
    type = 'legendbox'
    def __init__(self, x, y, style=None):
        self.x = x
        self.y = y
        self.style = style or copy(default_legboxstyle)
        self.components = []

    def add(self, comp):
        self.components.append(comp)

    def write_xml(self, xml):
        xml.tag(self.type)
        self.style.write_xml(xml)
        xml.empty('position', x=self.x, y=self.y)
        for c in self.components:
            xml.empty('component', ref=c._id)
        xml.endtag(self.type)

class Plot(object):
    def __init__(self):
        self.title = ''
        self.xrange = None
        self.yrange = None
        self.xlabel = ''
        self.ylabel = ''
        self._types = {}

    def add(self, c):
        self._types.setdefault(c.type, []).append(c)

    def get_type(self, typename):
        return self._types.get(typename, [])

    def write_xml(self, xml, is_toplevel=1):
        if is_toplevel:
            xml.toplevel()
        xml.tag('plot')
        xml.node('title', self.title)
        if self.xrange:
            xml.empty('xrange', lower=self.xrange[0],
                      upper=self.xrange[1])
        if self.yrange:
            xml.empty('yrange', lower=self.yrange[0],
                      upper=self.yrange[1])
        xml.node('xlabel', self.xlabel)
        xml.node('ylabel', self.ylabel)
        for v in self._types.values():
            for c in v:
                c.write_xml(xml)
        xml.endtag('plot')

_linetypes = ['solid', 'dotted', 'dotdashed', 'shortdashed',
              'longdashed', 'dotdotdashed', 'dotdotdotdashed']
def new_linetype(i):
    return _linetypes[i % len(_linetypes)]

biggles_colours = {'black'   : 'solid',
                   'blue'    : 'dotted',
                   'purple'  : 'dotdashed',
                   'yellow'  : 'shortdashed',
                   'red'     : 'longdashed',
                   'brown'   : 'dotdotdashed',
                   'green'   : 'dotdotdotdashed'
                   }

biggles_style = [('colour', 'color', 'black', str),
                 ('linetype', 'linetype', 'solid', str),
                 ('linewidth', 'linewidth', None, float),
                 ('symbolsize', 'symbolsize', None, float),
                 ('symboltype', 'symboltype', None, str),
                ]
_face_map = {'serif' : 'HersheySerif',
             'sans-serif' : 'HersheySansSerif'}
def _face_conv(x):
    return _face_map.get(x, x)
biggles_textstyle = [('face', 'fontface', 'serif', _face_conv),
                     ('size', 'fontsize', None, float),
                     ('halign', 'texthalign', 'center', str),
                     ('valign', 'textvalign', 'center', str)]
biggles_legendstyle = biggles_textstyle[:] + \
        [('width', 'key_width', None, float),
         ('height', 'key_height', None, float),
         ('hsep', 'key_hsep', None, float),
         ('vsep', 'key_vsep', None, float)]

def create_dict(style, biggles_defaults):
    D = {}
    for stylename, bgname, default, converter in biggles_defaults:
        if converter is None:
            converter = lambda x: x
        if default is None:
            if hasattr(style, stylename):
                bg = style.get(stylename)
                if bg is not None:
                    D[bgname] = converter(bg)
        else:
            D[bgname] = converter(style.get(stylename, default))
    return D

def style2biggles(style, is_bw=0):
    D = create_dict(style, biggles_style)
    if is_bw:
        D['linetype'] = style.get('bw_linetype',
                                  biggles_colours.get(D['color'], 'solid'))
        D['color'] = 'black'
    return D

def textstyle2biggles(tstyle):
    D = create_dict(tstyle, biggles_textstyle)
    return D

def plot2biggles(p, is_bw=0):
    import biggles
    pbg = biggles.FramedPlot()
    pbg.title = p.title
    pbg.x1.label = p.xlabel
    pbg.y1.label = p.ylabel
    pbg.xrange = p.xrange
    pbg.yrange = p.yrange
    bg_curves = {}
    for c in p.get_type('curve'):
        d = style2biggles(c.style, is_bw=is_bw)
        x = c.xydata.x()
        y = c.xydata.y()
        if c.style.get('linetype', None) != 'noline':
            bg_c = biggles.Curve(x, y, **d)
        else:
            del d['linetype']
            d['type'] = c.style.get('symbol', 'cross')
            d['size'] = int(c.style.get('symbol_size', 1))
            bg_c = biggles.Points(x, y, **d)
        bg_curves[c] = bg_c
        pbg.add(bg_c)
    for t in p.get_type('label'):
        d = textstyle2biggles(t.style)
        pbg.add(biggles.DataLabel(t.x, t.y, t.text, **d))
    for pk in p.get_type('legendbox'):
        # more than one legend box? Let the user decide :-)
        d = create_dict(pk.style, biggles_legendstyle)
        pk_comps = []
        for c in pk.components:
            bg_c = bg_curves[c]
            bg_c.label = c.legend
            pk_comps.append(bg_c)
        pbg.add(biggles.PlotKey(pk.x, pk.y, pk_comps, **d))
    return pbg

def plot2gracefile(p, fileName):
    """
    Dump the data from a plot to a Grace .agr file.
    """
    fo = open(fileName, 'w')
    fo.write('@with g0\n')
    if p.xrange and p.yrange:
        fo.write('@    world %g, %g, %g, %g\n'%(p.xrange[0], p.yrange[0],
                                                p.xrange[1], p.yrange[1]))
    fo.write('@    title "%s"\n' % (p.title,))
    fo.write('@    xaxis on\n')
    fo.write('@    xaxis label "%s"\n' % (p.xlabel,))
    fo.write('@    yaxis on\n')
    fo.write('@    yaxis label "%s"\n' % (p.ylabel,))
    legendBoxes = p.get_type('legendbox')
    if legendBoxes:
        legendBox = legendBoxes[0]
        fo.write('@    legend on\n')
        fo.write('@    legend loctype world\n')
        fo.write('@    legend %g, %g\n' % (legendBox.x, legendBox.y))
    for i, c in enumerate(p.get_type('curve')):
        fo.write('@    s%d type xy\n' % i)
        fo.write('@    s%d hidden false\n' % i)
        fo.write('@    s%d legend "%s"\n' % (i, c.legend))
    for i, c in enumerate(p.get_type('curve')):
        fo.write('@target G0.S%d\n' % i)
        fo.write('@type xy\n')
        for x, y in c.xydata.data:
            fo.write('  %.16g %.16g\n' % (x,y))
        fo.write('&\n')
    fo.close()

def plot2grace(p):
    from gracePlot import gracePlot
    pgr = gracePlot()
    pgr.hold(1)
    pgr.title(p.title)
    pgr.xlabel(p.xlabel)
    pgr.ylabel(p.ylabel)
    if p.xrange:
        pgr.xlimit(p.xrange[0], p.xrange[1])
    if p.yrange:
        pgr.ylimit(p.yrange[0], p.yrange[1])
    # FIXME: styles are ignored for now
    for c in p.get_type('curve'):
        x = c.xydata.x()
        y = c.xydata.y()
        pgr.plot(x,y)
    # FIXME: text labels
    # FIXME: legend box position
    for lg in p.get_type('legendbox'):
        labels = []
        for c in lg.components:
            labels.append(c.legend)
        pgr.legend(labels)
    return pgr

def add_optik_options(parser):
    parser.add_option('--bw', action="store_true", default=0,
                      dest="bw", help="do plot in black-and-white")
    parser.add_option('--show', action="store_true", default=0,
                      dest="show",
                      help="show plot in X window")
    parser.add_option('--format', action="store", type="string",
                      dest="img_fmt", default="eps",
                      help="format to save plot as")
    parser.add_option('--no-xml', action="store_false", default=1,
                      dest="xml", help="don't write xml version of plot")

def simple_optik_options():
    from optparse import OptionParser
    parser = OptionParser()
    add_optik_options(parser)
    options, args = parser.parse_args()
    return options

def save_plot(plot, file_base, options):
    pbg = plot2biggles(plot, is_bw = options.bw)
    img_fmt = options.img_fmt.lower()
    if img_fmt == "eps":
        pbg.write_eps(file_base + '.eps')
    else:
        pbg.write_img(img_fmt, 500, 500, '%s.%s'%(file_base,img_fmt))

    if options.show:
        pbg.show()

    if options.xml:
        xml = XMLWriter('%s.xml'%file_base, indent=4)
        plot.write_xml(xml)
