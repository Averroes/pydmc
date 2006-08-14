import os, os.path
import sys
import tempfile

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

def filter_file(infile, outfile, cmd, replace=False):
    """Filter a file using the python function `cmd`, optionally replacing
    the original file.

    If `infile` is `None`, `sys.stdin` is used. If `outfile` is `None`,
    `sys.stdout` is used.
    """
    if infile is None:
        in_fo = sys.stdin
        replace = False
    else:
        in_fo = open(infile, 'r')
    if outfile is None:
        out_fo = sys.stdout
    elif replace:
        out_fo = ReplacingOutputFile(infile)
    else:
        out_fo = open(outfile, 'w')
    try:
        try:
            changes_made = cmd(in_fo, out_fo)
        except:
            # don't overwrite input file if there was an error
            if out_fo != sys.stdout: out_fo.close()
            raise
    finally:
        if in_fo != sys.stdin: in_fo.close()
    if replace and changes_made:
        out_fo.close(replace=True)
    else:
        out_fo.close()

if __name__ == '__main__':
    import pydmc.simpletest
    pydmc.simpletest.main()
