import os
import sys
import tempfile

from pydmc.util import is_string, null

def quote_shell(s):
    """Quote a string for passing as an argument to a shell command.
    """
    # replace literal ' with a close ', a \', and an open '
    s = s.replace("'", r"'\''")
    return "'" + s + "'"

def _test_quote():
    assert quote_shell("abc") == "'abc'"
    assert quote_shell("'abc'") == r"''\''abc'\'''"
    assert quote_shell("$abc") == "'$abc'"

class SubCommandError(Exception):
    """Exception raised if a shell command returned with a non-zero
    exit status, or was killed by a signal"""
    def __init__(self, cmd, status):
        self.cmd = cmd
        self.status = status
    def __str__(self):
        if not os.WIFEXITED(self.status):
            return "'%s' failed to exit properly"%(self.cmd,)
        else:
            return "'%s' exited with non-zero status %d"%(
                            self.cmd, os.WEXITSTATUS(self.status))

def cmd(cmd):
    """Run a command using os.system, raising an exception if it failed"""
    status = os.system(cmd)
    if not (os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0):
        raise SubCommandError(cmd, status)

class ReplacingOutputFile(object):
    """A file object, when closed, overwrites the original file."""
    def __init__(self, infile, mode='w+b'):
        self._infile = infile
        fd, outfile = tempfile.mkstemp(dir=os.path.dirname(infile))
        self.name = outfile
        st = os.stat(infile)
        os.chmod(outfile, st.st_mode & 07777)
        self.file = os.fdopen(fd, mode, -1)
        self.close_called = False

    def __getattr__(self, name):
        file = self.__dict__['file']
        a = getattr(file, name)
        if not isinstance(a, int):
            setattr(self, name, a)
        return a

    def close(self, replace=False):
        if not self.close_called:
            self.close_called = True
            self.file.close()
            if replace:
                # move temporary file safely over input file
                os.rename(self.name, self._infile)
            else:
                os.unlink(self.name)

    def __del__(self):
        self.close()

def open_file(filename, mode, default):
    if filename is None:
        fo = default
        closer = null
    elif is_string(filename):
        fo = open(filename, mode)
        closer = fo.close
    else:
        fo = filename
        closer = null
    return fo, closer

def filter_file(cmd, infile=None, outfile=None, replace=False):
    """Filter a file using the python function `cmd`, optionally replacing
    the original file.

    If `infile` is `None`, `sys.stdin` is used. If `outfile` is `None`,
    `sys.stdout` is used.

    `cmd` should return `True` if changes were made.
    """
    if replace:
        if infile is None:
            raise ValueError("can't replace sys.stdin")
        if outfile is not None:
            raise ValueError("can't specify an output file when replace=True")
    in_fo, close_in = open_file(infile, 'r', sys.stdin)
    if replace:
        out_fo = ReplacingOutputFile(in_fo.name)
        close_out = out_fo.close
    else:
        out_fo, close_out = open_file(outfile, 'w', sys.stdout)
    try:
        try:
            changes_made = cmd(in_fo, out_fo)
        except:
            close_out()
            raise
    finally:
        close_in()
    if replace and changes_made:
        out_fo.close(replace=True)
    else:
        close_out()

if __name__ == '__main__':
    import pydmc.simpletest
    pydmc.simpletest.main()
