__all__ = ['DataFileError', 'Column', 'FloatCol', 'IntCol', 'StrCol',
           'TextDataWriter', 'TextDataReader']

import re
import numpy

try:
    from pysqlite2 import dbapi2 as sqlite
except ImportError:
    pass

from pydmc.util import is_string, is_sequence

class DataFileError(Exception):
    pass

COLTYPE_MAP = {float : 'float', int : 'int', str : 'str', unicode : 'str'}
COLTYPE_REV_MAP = {}
for k in COLTYPE_MAP:
    COLTYPE_REV_MAP[COLTYPE_MAP[k]] = k

class Column(object):
    """Base type for a column in a data file.
    """
    def __init__(self, name, type=None, length=1, fmt='%r', typename=None):
        self.name = name
        if typename is None:
            typename = COLTYPE_MAP[type]
        self.type_name = typename
        if type is None:
            type = COLTYPE_REV_MAP[self.type_name]
        self.type = type
        self.length = length
        self._format = fmt

    def __str__(self):
        """Looks like name(type)[length]"""
        s = self.name
        if self.type_name != 'float':
            s += '(%s)' % self.type_name
        if self.length != 1:
            s += '[%s]' % self.length
        return s

    def __repr__(self):
        return '%s(%r,length=%d,fmt=%r,typename=%r)' % (
            self.__class__.__name__, self.name, self.length,
            self._format, self.type_name)

    def get_length(self, metadata):
        return metadata.get(self.length, self.length)

    def format(self, d):
        return self._format % d

    def parse(self, d):
        return self.type(d)

    def to_array(self, d):
        return numpy.asarray(d)

class FloatCol(Column):
    """Special case for a float. The representation tries not to look like
    an integer (1.0 instead of 1)."""
    def __init__(self, name, length=1, fmt='%.17g'):
        Column.__init__(self, name, type=float, length=length, fmt=fmt)

    def format(self, d):
        # special case so that we always have a decimal point if it comes out
        # as an integer.
        s = self._format % d
        if not re.match('-?[0-9]+$', s):
            return s
        s += '.0'
        return s

    def to_array(self, d):
        return numpy.asarray(d, type=float)

class IntCol(Column):
    """A column of integer(s)."""
    def __init__(self, name, length=1, fmt='%d'):
        Column.__init__(self, name, type=int, length=length, fmt=fmt)

    def to_array(self, d):
        return numpy.asarray(d, type=int)

class StringCol(Column):
    """A column of a string."""
    def __init__(self, name, fmt='%r'):
        Column.__init__(self, name, type=str, length=1, fmt=fmt)

COL_TYPES = {float : FloatCol, int : IntCol, str : StringCol}
def coerce_columns(columns):
    new_columns = []
    for c in columns:
        if isinstance(c, Column):
            new_columns.append(c)
        elif is_string(c):
            # assume float by default
            new_columns.append(Column(c, type=float))
        else:
            name, ty = c
            if ty in COL_TYPES:
                col = COL_TYPES[ty](name)
            else:
                col = Column(name, ty)
            new_columns.append(col)
    return new_columns

def timestamp():
    import datetime
    now = datetime.datetime.now()
    value = now.isoformat(' ')
    return value

class DataWriter(object):
    """I am the base class for data writers.
    """
    def __init__(self, columns=None):
        super(DataWriter, self).__init__()
        if columns is not None:
            columns = coerce_columns(columns)
        self.column_descriptions = columns
        self.metadata = {}
        self._have_added_column_descriptions = False

    def add_metadata(self, key, value, fmt='%r'):
        if fmt.count('%') != 1:
            raise DataFileError('fmt %r is not a valid formatting code' % fmt)
        self.metadata[key] = value

    def add_comment(self, msg):
        "For some implementations, this does nothing."
        pass

    def add_timestamp(self, key='timestamp'):
        """Add a timestamp to the metadata, in ISO 8601 format,
        YYYY-MM-DD HH:MM:SS[.mmmmmm][+HH:MM]. The key name defaults to
        'timestamp'."""
        value = timestamp()
        self.add_metadata(key, value)

    def determine_columns(self, data):
        """Guess column types from the data.

        There should be no need to override this.
        """
        columns = []
        for n, d in enumerate(data):
            name = 'col%d' % n
            if is_string(d):
                columns.append(StringCol(name))
                continue
            elif is_sequence(d):
                t = type(d[0])
                l = len(d)
            else:
                t = type(d)
                l = 1
            if t is float:
                columns.append(FloatCol(name, length=l))
            else:
                columns.append(Column(name, type=t, length=l))
        return columns

    def _add_column_descriptions(self):
        # subclasses should set self._have_added_column_descriptions to True
        # when they are done.
        pass

    def _check_column_descriptions(self, data):
        if not self._have_added_column_descriptions:
            # create the column descriptions if necessary
            if self.column_descriptions is None:
                self.column_descriptions = self.determine_columns(data)
            # now, check that the lengths are good
            for c in self.column_descriptions:
                if is_string(c.length):
                    if c.length not in self.metadata:
                        raise DataFileError(
                            'could not find length %r for column %r in metadata'
                            % (c.length, c.name))
            self._add_column_descriptions()
        if len(self.column_descriptions) != len(data):
            raise DataFileError('data does not match column description')

    def append(self, *data):
        self._check_column_descriptions(data)
        for c, d in zip(self.column_descriptions, data):
            clength = self.metadata.get(c.length, c.length)
            if is_sequence(d):
                if len(d) != clength:
                    raise DataFileError('data for column %r has '
                                        'invalid length' % (c.name))

    def write_all(self, data):
        for d in data:
            self.append(*d)

    def flush(self):
        pass

    def finish(self):
        pass

    def close(self):
        self.finish()

class TextDataWriter(DataWriter):
    """Write data to a text file in a easily-parsable format.

    Metadata-lines start with #m
    Comments start with #
    The description of the columns starts with #c
    Each line is (by default) a tab-separated line of numbers.
    """
    def __init__(self, fo, columns = None, separator='\t'):
        super(TextDataWriter, self).__init__(columns)
        if is_string(fo):
            fo = open(fo, 'w', 1)
        self.fo = fo
        self.separator = separator

    def add_metadata(self, key, value, fmt='%r'):
        super(TextDataWriter, self).add_metadata(key, value, fmt=fmt)
        self.fo.write( ('#m %s = '+fmt+'\n') % (key, value))

    def add_comment(self, msg):
        super(TextDataWriter, self).add_comment(msg)
        self.fo.write('# %s\n'%msg)

    def _add_column_descriptions(self):
        super(TextDataWriter, self)._add_column_descriptions()
        cdline = [str(c) for c in self.column_descriptions]
        self.fo.write('#c ')
        self.fo.write('  '.join(cdline))
        self.fo.write('\n')
        self._have_added_column_descriptions = True

    def append(self, *data):
        """Adds the arguments to the data file.

        This will output the column description automatically, and will
        even determine a reasonable one if one wasn't provided to the
        constructor.
        """
        super(TextDataWriter, self).append(*data)
        dline = []
        for c, d in zip(self.column_descriptions, data):
            if is_sequence(d):
                for x in d:
                    dline.append(c.format(x))
            else:
                dline.append(c.format(d))
        self.fo.write(self.separator.join(dline))
        self.fo.write('\n')

    def flush(self):
        super(TextDataWriter, self).flush()
        self.fo.flush()

    def close(self):
        super(TextDataWriter, self).close()
        self.fo.close()


class SqliteDataWriter(DataWriter):
    METADATA_TABLE='metadata'
    COMMENTS_TABLE='comments'
    DATA_TABLE = 'data'

    # note that I've chosen REAL as the type for float, as with SQLite 3
    # more efficient storage will be used for that.
    SQL_TYPE_MAP = {'int' : 'INTEGER', 'float' : 'REAL', 'str' : 'TEXT'}

    def __init__(self, db, columns, column_array_separator='_',
                 index_column_name='_index_'):
        super(SqliteDataWriter, self).__init__(columns)
        if is_string(db):
            db = sqlite.connect(db)
        self.dbconn = db
        self.column_array_separator = column_array_separator
        self._create_tables()
        self.index_column_name = index_column_name
        self._comment_idx = 0
        self._data_sql = None

    def _create_a_table(self, name, structure):
        cu = self.dbconn.cursor()
        sql = 'CREATE TABLE %s (%s)' % (name, structure)
        cu.execute(sql)
        self.dbconn.commit()

    def _create_tables(self):
        self._create_a_table(self.METADATA_TABLE, 'key TEXT, value TEXT')
        self._create_a_table(self.COMMENTS_TABLE,
                             'id INTEGER PRIMARY KEY, comment TEXT')

    def add_metadata(self, key, value, fmt='%r'):
        super(SqliteDataWriter, self).add_metadata(key, value, fmt=fmt)
        svalue = fmt % (value,)
        cu = self.dbconn.cursor()
        sql = 'INSERT OR REPLACE INTO %s (key, value) VALUES (?, ?)' % (
                                            self.METADATA_TABLE,)
        cu.execute(sql, (key, svalue))
        self.dbconn.commit()

    def add_comment(self, msg):
        super(SqliteDataWriter, self).add_comment(msg)
        cu = self.dbconn.cursor()
        # use NULL for index for autoincrement
        sql = 'INSERT INTO %s (comment) VALUES (?)' % (self.COMMENTS_TABLE,)
        cu.execute(sql, (msg,))
        self.dbconn.commit()

    def get_column_length(self, c):
        if is_string(c.length):
            try:
                cl = self.metadata[c.length]
            except KeyError:
                raise DataFileError(
                    'SqliteDataWriter needs the column length defined '
                    '(for column %r)' % (c,))
        else:
            cl = c.length
        return cl

    def _add_column_descriptions(self):
        super(SqliteDataWriter, self)._add_column_descriptions()
        self.add_metadata('$index_column$', self.index_column_name)
        cds = ['%s INTEGER PRIMARY KEY' % (self.index_column_name,)]
        cas = self.column_array_separator
        for c in self.column_descriptions:
            sql_type = self.SQL_TYPE_MAP.get(c.type_name, 'TEXT')
            cl = self.get_column_length(c)
            if cl == 1:
                cds.append( '%s %s' % (c.name, sql_type) )
            else:
                for i in range(c.length):
                    cds.append( '%s%s%d %s' % (c.name, cas, i+1, sql_type) )
        structure = ', '.join(cds)
        self._create_a_table(self.DATA_TABLE, structure)
        self._have_added_column_descriptions = True

    def _create_data_sql(self, data):
        if self._data_sql is not None:
            return self._data_sql
        columns_fmt = []
        columns = []
        values = []
        cas = self.column_array_separator
        for c, d in zip(self.column_descriptions, data):
            cl = self.get_column_length(c)
            if is_sequence(d):
                if len(d) != cl:
                    raise DataFileError("data column has wrong length")
                for i in range(cl):
                    columns_fmt.append('?')
                    columns.append('%s%s%d' % (c.name, cas, i+1))
                for x in d:
                    values.append(x)
            else:
                if cl != 1:
                    raise DataFileError("data column has wrong length")
                columns_fmt.append('?')
                columns.append(c.name)
                values.append(d)
        scolumns_fmt = ','.join(columns_fmt)
        sql ='INSERT INTO %s (%s) VALUES (%s)' % (self.DATA_TABLE,
                                                  ', '.join(columns),
                                                  scolumns_fmt)
        self._data_sql = sql
        return sql

    def _coerce_data(self, data):
        values = []
        for c, d in zip(self.column_descriptions, data):
            cl = self.get_column_length(c)
            if is_sequence(d):
                if len(d) != cl:
                    raise DataFileError("data column has wrong length")
                values.extend(list(d))
            else:
                if cl != 1:
                    raise DataFileError("data column has wrong length")
                values.append(d)
        return values

    def append(self, *data):
        super(SqliteDataWriter, self).append(*data)
        sql = self._create_data_sql(data)
        values = self._coerce_data(data)
        cu = self.dbconn.cursor()
        cu.execute(sql, values)
        self.dbconn.commit()

    def write_all(self, data):
        idata = iter(data)
        data0 = idata.next()
        # this sets up the appropiate tables and column descriptions
        self.append(*data0)
        sql = self._create_data_sql(data0)
        cu = self.dbconn.cursor()
        def value_generator():
            for d in idata:
                yield self._coerce_data(d)
        cu.executemany(sql, value_generator())
        self.dbconn.commit()

    def close(self):
        super(SqliteDataWriter, self).close()
        self.dbconn.close()


class TextDataReader(object):
    """Read a data file written by TextDataWriter.

    Instance variables:

    metadata : { (name : value) }
        mapping from metadata keys to values. If guess_metadata_type is set to
        true in __init__, then the type of the values are the 'best-fit':
        integers, floats, or strings (quoted or unquoted).

    column_descriptions : [ Column ]
        List of column objects decribing the columns.

    coerce_to_array : bool
        If true, return columns as numpy arrays. Set to false to return lists.

    """
    _METADATA_STRICT_PAT = \
                   re.compile(r'^#m\s+(?P<key>.*?)\s*[:=]\s*(?P<value>.*)\s*$')
    _METADATA_LOOSE_PAT = \
                   re.compile(r'^#\s*(?P<key>.*?)\s*[:=]\s*(?P<value>.*)\s*$')
    _IGNORE_PAT = re.compile(r'(?:^#)|(?:^\s*$)')
    _COLUMN_DEF_PAT = re.compile(r'^#c (.*)$')
    _COLUMN_PAT = re.compile(r'(?P<name>\w+)'
                            r'(?:\((?P<type>\w+)\))?'
                            r'(?:\[(?P<length>\w+)\])?')

    def __init__(self, fo, columns = None,
                 guess_metadata_type = True,
                 loose_metadata = False,
                 coerce_to_array = True):
        """
        fo : file | string
            The file to read, as either a file-like object, or a file name. If
            a file name, this object will take care of closing it once the
            data is read; otherwise, the caller is responsible.
        columns : [ Column ]
            List of Column objects desribing the columns, or None to read
            them from the data file
        guess_metadata_type : bool
            By default, convert integer- and float-like things in metadata to
            those types. Set this to false to turn this behaviour off.
        loose_metadata : bool
            By default, be stricter on the format of the metadata. This is the
            format written by TextDataWriter. Set this to false to assume
            anything looking like '# key = value' is metadata. Useful for data
            files done by hand.
        coerce_to_array : bool
            By default, return columns as numpy arrays. Set to false to
            return as lists.
        """
        if is_string(fo):
            our_fo = True
            fo = open(fo, 'rU')
        else:
            our_fo = False
        self.metadata = {}
        self._data = []
        if loose_metadata:
            self._metadata_pat = self._METADATA_LOOSE_PAT
        else:
            self._metadata_pat = self._METADATA_STRICT_PAT
        self._guess_metadata_type = guess_metadata_type
        self.coerce_to_array = coerce_to_array
        self.column_descriptions = columns
        self.read(fo)
        if our_fo:
            fo.close()

    def column_names():
        "List of column names."
        def fget(self):
            return [ c.name for c in self.column_descriptions ]
        return locals()
    column_names = property(**column_names())

    def data():
        def fget(self):
            return self._data
        return locals()
    data = property(**data())

    def read(self, fo):
        for line in fo:
            m = self._metadata_pat.match(line)
            if m:
                self._parse_metadata(m)
                continue
            m = self._COLUMN_DEF_PAT.match(line)
            if m:
                self._parse_column_description(m)
                continue
            m = self._IGNORE_PAT.match(line)
            if m:
                continue
            self._append_data_line(line)

    def _parse_metadata(self, match):
        key = match.group('key')
        value = match.group('value')
        if self._guess_metadata_type:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    if ((value.startswith("'") and value.endswith("'"))
                        or (value.startswith('"') and value.endswith('"'))):
                        value = value[1:-1]
        self.metadata[key] = value

    def _parse_column_description(self, match):
        if self.column_descriptions is not None:
            return
        cdefslist = match.group(1).split()
        cdefs = []
        for cs in cdefslist:
            m = self._COLUMN_PAT.match(cs)
            if not m:
                raise DataFileError('could not parse column definition %r'%cs)
            cname = m.group('name')
            clength = m.group('length')
            if clength is None:
                clength = 1
            try:
                clength = int(clength)
            except ValueError:
                try:
                    clength = self.metadata[clength]
                except KeyError:
                    raise DataFileError(
                        "could not find length %r of column %r"%(clength, cname))
            ctypename = m.group('type')
            if ctypename is None:
                ctypename = 'float'
            cd = Column(cname, typename=ctypename, length=clength)
            cdefs.append(cd)
        self.column_descriptions = cdefs

    def _determine_columns(self, line):
        sdata = line.split()
        cdefs = []
        for n, sd in enumerate(sdata):
            name = 'col%d' % n
            try:
                d = int(sd)
            except ValueError:
                try:
                    d = float(sd)
                except ValueError:
                    c = StringCol(name)
                else:
                    c = FloatCol(name)
            else:
                c = IntCol(name)
            cdefs.append(c)
        self.column_descriptions = cdefs

    def _append_data_line(self, line):
        if self.column_descriptions is None:
            self._determine_columns(line)
        sdata = line.split()
        data = []
        n = 0
        for cd in self.column_descriptions:
            clength = cd.get_length(self.metadata)
            if clength == 1:
                d = cd.parse(sdata[n])
                data.append(d)
                n += 1
            else:
                d = []
                for i in range(clength):
                    x = cd.parse(sdata[n])
                    d.append(x)
                    n += 1
                data.append(tuple(d))
        self._data.append(tuple(data))

    def row(self, n):
        return self._data[n]

    def column_position(self, col):
        for n, c in enumerate(self.column_names):
            if col == c:
                return n
        return col

    def describe_column(self, col):
        col_num = self.column_position(col)
        return self.column_descriptions[col_num]

    def column(self, col, index=None):
        col_num = self.column_position(col)
        if index is not None:
            data = [ d[col_num][index] for d in self._data ]
        else:
            data = [ d[col_num] for d in self._data ]
        if self.coerce_to_array:
            cd = self.column_descriptions[col_num]
            return cd.to_array(data)
        else:
            return data

    def __iter__(self):
        return self.data

class ParameterWriter(object):
    def __init__(self):
        super(ParameterWriter, self).__init__()
        self._added_variables = set()

    def add_comment(self, msg):
        pass

    def add_timestamp(self, key='timestamp'):
        value = timestamp()
        self.add(key, value)

    def _add_variable(self, key):
        if key in self._added_variables:
            raise ValueError('key %s has already been added' % (key,))
        self._added_variables.add(key)

    def add_scalar(self, key, value):
        self._add_variable(key)

    def add_array(self, key, value):
        self._add_variable(key)

    def add(self, key, value):
        if is_sequence(value):
            self.add_array(key, value)
        else:
            self.add_scalar(key, value)

    def flush(self):
        pass

    def finish(self):
        pass

    def close(self):
        self.finish()

def coerceTypecode(a):
    thisType = a.dtype.type
    if issubclass(thisType, numpy.floating):
        return 'float'
    elif issubclass(thisType, numpy.integer):
        return 'int'
    return None

class SimpleParameterWriter(ParameterWriter):
    def __init__(self, fo):
        super(SimpleParameterWriter, self).__init__()
        if is_string(fo):
            fo = open(fo, 'w')
        self.fo = fo

    def add_comment(self, msg):
        super(SimpleParameterWriter, self).add_comment(msg)
        msg = msg.replace('\n', '\n# ')
        self.fo.write('# ')
        self.fo.write(msg)
        self.fo.write('\n')

    def add_scalar(self, key, value):
        super(SimpleParameterWriter, self).add_scalar(key, value)
        if isinstance(value, int):
            typecode = 'int'
            s_value = repr(value)
        elif isinstance(value, float):
            typecode = 'float'
            s_value = repr(value)
        elif is_string(value):
            typecode = 'string'
            value = value.replace('\\', r'\\')
            value = value.replace('\n', r'\n')
            value = value.replace('"', r'\"')
            s_value = '"' + value + '"'
        else:
            typecode = 'unknown'
            s_value = repr(value)
        self.fo.write('scalar %s %s %s\n' % (key, typecode, s_value))

    def add_array(self, key, value):
        super(SimpleParameterWriter, self).add_array(key, value)
        a = numpy.asarray(value)
        rank = len(a.shape)
        self.fo.write('array %s %s %d %s\n' % (key, coerceTypecode(a),
                                               rank,
                                               ' '.join(str(n) for n in a.shape)))
        for i in xrange(0, a.shape[0]):
            row = numpy.ravel(a[i])
            self.fo.write(' '.join(repr(v) for v in row))
            self.fo.write('\n')

    def flush(self):
        super(SimpleParameterWriter, self).flush()
        self.fo.flush()

    def close(self):
        super(SimpleParameterWriter, self).close()
        self.fo.close()

def tokenise_by_whitespace(fo_iter):
    for line in fo_iter:
        line = line.strip()
        for t in line.split():
            yield t

def _readScalar(line):
    name, typecode, s_value = rest.split(None, 2)
    if typecode == 'int':
        value = int(s_value)
    elif typecode == 'float':
        value = float(s_value)
    elif typecode == 'string':
        if not s_value.startswith('"') or not s_value.endswith('"'):
            raise ValueError("improperly quoted string")
        value = s_value[1:-1]
        value = value.replace(r'\"', '"')
        value = value.replace(r'\n', '\n')
        value = value.replace(r'\\', '\\')
    else:
        value = s_value
    return name, value

def _readArray(line, fo_iter):
    name, typecode, s_ndim, s_shape = rest.split(None, 3)
    ndim = int(s_ndim)
    shape = [int(s) for s in s_shape.split()]
    if typecode == 'int':
        converter = int
        atype = int
    elif typecode == 'float':
        converter = float
        atype = float
    else:
        raise ValueError("unknown array typecode %r" % (typecode,))
    totsize = reduce(lambda a,b:a*b, shape, 1)
    a = numpy.zeros((totsize,), type=atype)
    split_on_ws = tokenise_by_whitespace(fo_iter)
    for i in xrange(totsize):
        t = split_on_ws.next()
        a[i] = converter(t)
    a.resize(shape)
    return name, a

def _simpleParameterFileReader(fo):
    results = {}
    fo_iter = iter(fo)
    for line in fo_iter:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        first, rest = line.split(None, 1)
        if first == 'scalar':
            name, value = _readScalar(rest)
            results[name] = value
        elif first == 'array':
            name, a = _readArray(rest, fo_iter)
            results[name] = a
        else:
            raise ValueError("found %r, expected 'scalar' or 'array'"%(first,))
    return results

def readSimpleParameterFile(fo):
    if is_string(fo):
        our_fo = True
        fo = open(fo, 'rU')
    else:
        our_fo = False
    results = _simpleParameterFileReader(fo)
    if our_fo:
        fo.close()
    return results

def _test_data_writer():
    from cStringIO import StringIO
    fo = StringIO()
    dfw = TextDataWriter(fo,
                         [FloatCol('col1'),
                          FloatCol('col2',3, fmt='%.15g'),
                          IntCol('col3','length'),
                          IntCol('col4')],
                         separator=' ')
    dfw.add_metadata('length', 3)
    dfw.add_metadata('some metadata', (1,2,3))
    dfw.add_metadata('other stuff', 'hello')
    dfw.add_comment('this is a comment')
    dfw.append(1.31, (0.1, 0.2, 0.3), (4, 5, 6), 7)
    dfw.add_metadata('end', 'nothing')
    s = fo.getvalue()
    dfw.close()
    assert s == '''\
#m length = 3
#m some metadata = (1, 2, 3)
#m other stuff = 'hello'
# this is a comment
#c col1  col2[3]  col3(int)[length]  col4(int)
1.3100000000000001 0.1 0.2 0.3 4 5 6 7
#m end = 'nothing'
''', s

def _test_data_writer_auto():
    from cStringIO import StringIO
    fo = StringIO()
    dfw = TextDataWriter(fo)
    dfw.append(1.31, (1.0, 2, 3), 7)
    s = fo.getvalue()
    dfw.close()
    assert s == '''\
#c col0  col1[3]  col2(int)
1.3100000000000001\t1.0\t2.0\t3.0\t7
''', s

def _test_sqlite_data_writer():
    db = sqlite.connect(':memory:')
    dfw = SqliteDataWriter(db, [FloatCol('col1'), FloatCol('cola',3)])
    dfw.add_metadata('stuff', (1,2,3))
    dfw.add_comment('a comment')
    dfw.add_comment('another comment')
    dfw.append(1.0, (2,3,4))
    dfw.append(4.5, (5,6,7))
    dfw.write_all( ((6.0, (1,2,3)), (3.0, (6.,7,8))) )

def _test_data_reader():
    from cStringIO import StringIO
    datafile = '''\
#m metadata1 = hello
#m metadata2 = 1
#m key with spaces: (1,2,3)
#m length = 3
# a comment
#c col1  col2[3]  col3(int)[length]  col4(int)
1.2 0.1 0.2 0.3 4 5 6 7
4.5 0.3 0.3 0.3 1 2 3 9
#m ending data = 4.5
'''
    fo = StringIO(datafile)
    dfr = TextDataReader(fo, coerce_to_array = False)
    assert len(dfr.metadata) == 5, dfr.metadata
    assert dfr.metadata['metadata1'] == 'hello'
    assert dfr.metadata['metadata2'] == 1
    assert dfr.metadata['key with spaces'] == '(1,2,3)'
    assert dfr.metadata['length'] == 3
    assert dfr.metadata['ending data'] == 4.5
    assert dfr.column_names == ['col1', 'col2', 'col3', 'col4']
    assert len(dfr.data) == 2
    assert dfr.row(0) == (1.2, (0.1, 0.2, 0.3), (4, 5, 6), 7)
    assert dfr.row(1) == (4.5, (0.3, 0.3, 0.3), (1, 2, 3), 9)
    row0 = dfr.row(0)
    assert isinstance(row0[2][0], int)
    assert isinstance(row0[2][1], int)
    assert isinstance(row0[2][2], int)
    assert isinstance(row0[3], int)
    assert dfr.column('col1') == [1.2, 4.5]
    assert dfr.column(0) == [1.2, 4.5]

def _test_data_reader_auto():
    from cStringIO import StringIO
    datafile = '''\
# metadata1 = hello
#metadata2 = 1
# key with spaces: (1,2,3)
# a comment
1.2 0.1 4
4.5 0.3 6
'''
    fo = StringIO(datafile)
    dfr = TextDataReader(fo, guess_metadata_type=False, loose_metadata=True,
                         coerce_to_array = False)
    assert len(dfr.metadata) == 3
    assert dfr.metadata['metadata1'] == 'hello'
    assert dfr.metadata['metadata2'] == '1'
    assert dfr.metadata['key with spaces'] == '(1,2,3)'
    assert dfr.column_names == ['col0', 'col1', 'col2']
    assert isinstance(dfr.column_descriptions[0], FloatCol)
    assert isinstance(dfr.column_descriptions[1], FloatCol)
    assert isinstance(dfr.column_descriptions[2], IntCol)
    assert dfr.row(0) == (1.2, 0.1, 4)
    assert dfr.row(1) == (4.5, 0.3, 6)
    assert dfr.column(0) == [1.2, 4.5]

def _test_simple_parameter_writer():
    from cStringIO import StringIO
    fo = StringIO()
    spw = SimpleParameterWriter(fo)
    spw.add_comment("hello")
    spw.add('an_int', 1)
    spw.add('a_float', 2.0)
    spw.add('a_string', "hi")
    spw.add('a_2d_int_array', numpy.array([[1,2],[3,4]]))
    s = fo.getvalue()
    spw.close()
    assert s == '''\
# hello
scalar an_int int 1
scalar a_float float 2.0
scalar a_string string "hi"
array a_2d_int_array int 2 2 2
1 2
3 4
'''

if __name__ == '__main__':
    import pydmc.simpletest
    pydmc.simpletest.main()
