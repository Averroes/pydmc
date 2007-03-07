import fcntl
import os, os.path, errno
import time
import tempfile
import shutil
import weakref

__all__ = ['LockFileError', 'LockFile',
           'shared_lock', 'exclusive_lock', 'open_read_lock',
           'get_persistent_file_lock',
           'FileLock', 'WriteLockedFile',
           'ReadLock', 'WriteLock', 'AtomicWriteLock',
           'what_is_locked', 'NullFile',
           'backup_file']

class LockFileError(Exception):
    pass

def oserror(cmd, *args):
    try:
        result = cmd(*args)
    except OSError, e:
        return e.errno, None
    return 0, result

# A translation of Debian's liblockfile
class LockFile(object):
    def __init__(self, lockfile):
        self.lockfile = lockfile

    def create(self, retries=4):
        lockfile = self.lockfile
        fd, tmplock = tempfile.mkstemp(prefix=os.path.basename(lockfile),
                                       dir=os.path.dirname(lockfile))
        old_umask = os.umask(022)
        try:
            os.chmod(tmplock, 0644)
        finally:
            os.umask(old_umask)

        try:
            buf = str(os.getpid())
            written = os.write(fd, buf)
            os.close(fd)
            if written != len(buf):
                raise LockFileError("couldn't write temporary lock")

            dontsleep = True
            sleeptime = 0
            statfailed = 0
            # now try to link the temporary lock to the lock.
            for i in range(retries+1):
                if not dontsleep:
                    sleeptime = min(sleeptime+5, 60)
                    time.sleep(sleeptime)
                dontsleep = False
                os.link(tmplock, lockfile)
                st1 = os.lstat(tmplock)
                try:
                    st = os.lstat(lockfile)
                except OSError:
                    statfailed += 1
                    if statfailed > 5:
                        # Normally, this can't happen; either another
                        # process holds the lockfile or we do.
                        break
                    continue
                # See if we got the lock
                if st.st_rdev == st1.st_rdev and st.st_ino == st1.st_ino:
                    return
                statfailed = 0
                # If there is a lockfile and it is invalid, remove the lockfile
                if not lockfile_check(lockfile):
                    try: os.unlink(lockfile)
                    except OSError: pass
                    dontsleep = True
            raise LockFileError("Failed after maximum number of attempts")
        finally:
            try: os.unlink(tmplock)
            except OSError: pass

    def remove(self):
        """Remove a lockfile"""
        e, _ = oserror(os.unlink, self.lockfile)
        if e == 0 or e == errno.ENOENT:
            return True
        return False

    __enter__ = create

    def __exit__(self, t, v, tb):
        self.remove()

    def touch(self):
        """Touch a lock"""
        e, _ = oserror(os.utime, self.lockfile, None)
        return e == 0

    def check(self):
        """See if a valid lockfile is present.
        """
        try:
            st = os.stat(self.lockfile)
        except OSError:
            return False
        try:
            fd = os.open(self.lockfile, os.O_RDONLY)
            buf = os.read(fd, 16)
            st = os.fstat(fd)
            now = st.st_atime
            os.close(fd)
            pid = int(buf)
        except OSError:
            now = time.time()
            pid = 0
        if pid > 0:
            # If we have a pid, see if the process owning the lockfile
            # is still alive
            e, _ = oserror(os.kill, pid, 0)
            if e == 0 or e == errno.EPERM:
                return True
            elif e == errno.ESRCH:
                # no such process
                return False
            # fall through
        # without a pid in the lockfile, the lock is valid if it is newer
        # than 5 minutes
        if now < st.st_mtime + 300:
            return True
        return False

# the below locking stuff was originally part of pyCAPA

# use flock because that's what CAPA uses. It's also saner wrt child
# processes.

def shared_lock(fo):
    fcntl.flock(fo.fileno(), fcntl.LOCK_SH)

def exclusive_lock(fo):
    fcntl.flock(fo.fileno(), fcntl.LOCK_EX)

def open_read_lock(filename):
    fo = open(filename, 'rb')
    shared_lock(fo)
    return fo

# Use cases:
#
# 1) reading from a file, without conflicting with writers
#    - here, we just need a shared lock
# 2) read from a file, write back an updated file
#    - have to grab an exclusive lock for the read, write to a temporary
#      file, then move the temporary file over the original (which is
#      an atomic operation in POSIX).

class PersistentFileLock(object):
    """A reentrant lock object for a file.

    The read_from(reader) method opens the file, acquires a read lock,
    passes the file object to reader for reading, then closes the file.

    The write_to(writer) method opens the file, acquires an exclusive lock,
    passes the file object to writer for writing, then closes the file. If
    the file is locked by this process already, it uses a WriteLockedFile
    object to write to a temporary file instead, and move it to this file
    atomically on successful writing.

    This is modelled on threading.RLock(). Note that this only locks a
    file per instance; multiple instances on the same file will be confused.
    """
    def __init__(self, filename):
        self.filename = filename
        self._n_locks = 0
        self._fo = None

    def acquire(self):
        if self._n_locks == 0:
            self._fo = open_read_lock(self.filename)
        self._n_locks += 1

    __enter__ = acquire

    def release(self):
        self._n_locks -= 1
        if self._n_locks == 0:
            self._fo.close()
            self._fo = None

    def __exit__(self, t, v, tb):
        self.release()

    def locked(self):
        return self._n_locks > 0

    def __del__(self):
        self.release()

    def read_from(self, reader):
        fo = open_read_lock(self.filename)
        try:
            data = reader(fo)
        finally:
            fo.close()
        return data

    def write_to(self, writer, mode='w+b'):
        if not self.locked():
            # lock hasn't been acquired by this instance
            fo = open(self.filename, mode)
            exclusive_lock(fo)
            try:
                writer(fo)
            finally:
                fo.close()
        else:
            write_fo = WriteLockedFile(self._fo)
            try:
                writer(write_fo)
            except:
                write_fo.rollback()
                raise
            else:
                write_fo.close()
            # old file object is invalid now (points to old file)
            # lock the new file
            self._fo.close()
            self._fo = open_read_lock(self.filename)

_file_locks = weakref.WeakValueDictionary()
def get_persistent_file_lock(filename):
    """
    Return a reentrant file lock object.

    Will return a previous instance if one exists; effectively, we try to
    have one and only one lock object per file in this process.
    """
    filename = os.path.absname(filename)
    fl = _file_locks.get(filename, None)
    if fl is None:
        fl = PersistentFileLock(filename)
        _file_locks[filename] = fl
    return fl

# XXX Why do we need this? Why can't PersistentFileLock do this?
class FileLock(object):
    """
    A file lock that can be acquired and released multiple times.
    """
    def __init__(self, filename):
        self.filename = filename
        self._fl = None

    def acquire(self):
        """Acquire the file lock.

        Can be called multiple times; only locks the file once.
        """
        if self._fl is None:
            self._fl = get_persistent_file_lock(self.filename)
            self._fl.acquire()

    def release(self):
        """Release the file lock.

        Can be called multiple times; only unlocks it once (if locked).
        """
        if self._fl is not None:
            self._fl.release()
            self._fl = None

    def is_locked(self):
        return self._fl is not None

    def read_from(self, reader):
        return self._fl.read_from(reader)
    def write_to(self, writer):
        self._fl.write_to(writer)

def what_is_locked():
    are_locked = []
    for filename in _file_locks:
        fl = _file_locks[filename]
        if fl.locked():
            are_locked.append( (fl.filename, fl._n_locks) )
    return are_locked

class NullFile(object):
    def __init__(self):
        object.__init__(self)
        self.closed = 0
    def close(self):
        self.closed = 1

class WriteLockedFile(object):
    """
    I am a writeable file object which locks the file being written to,
    writes to a temporary file, then moves the temporary file to
    the original atomically when closed.

    Use this to update a file without another writer interfering.
    """
    _tmp_fo = None
    def __init__(self, fo, file_name=None, backup_file=None,
                 keep_backup=True,
                 close_callback=None):
        object.__init__(self)
        self._close_callback = close_callback
        if file_name is None:
            file_name = fo.name
        if backup_file is None:
            backup_file = file_name + '~'
        self.backup_file = backup_file

        self.name = file_name
        self._fo_real = fo
        # get an exclusive lock on the original file to prevent other
        # processes from updating while we are
        try:
            exclusive_lock(self._fo_real)
        except IOError:
            self._fo_real = NullFile()

        # create a temporary file that we will operate on. Put it in the same
        # directory, so we're sure it's on the same filesystem.
        fd, tmpname = tempfile.mkstemp(prefix=os.path.basename(file_name)+'.',
                                       dir=os.path.dirname(file_name))
        self._tmp_fo = os.fdopen(fd, 'w+b', -1)
        self._tmp_name = tmpname

        # backup
        try:
            os.unlink(backup_file)
        except OSError:
            # fails if there isn't a backup file already
            pass
        # make a hard link for backup
        try:
            os.link(file_name, backup_file)
        except OSError:
            # fails if we're writing to a new file
            pass

        # setting this also indicates we finished init'ing properly
        self.closed = False

    def rollback(self):
        self._tmp_fo.close()
        try:
            os.unlink(self._tmp_name)
        except OSError:
            pass

    def commit(self):
        if not self.closed:
            # move the temporary file to the real file, removing the old
            # if necessary
            # note POSIX says this is atomic
            os.rename(self._tmp_name, self.name)
            if not self.keep_backup:
                try:
                    os.unlink(self.backup_file)
                except OSError:
                    pass
            self._fo_real.close()
            self._tmp_fo.close()
            if callable(self._close_callback):
                self._close_callback()
            self.closed = True

    def close(self):
        self.commit()

    def __del__(self):
        # only cleanup if we managed to go through all of __init__ without
        # errors
        if not hasattr(self, 'closed'):
            return
        self.close()

    def __getattr__(self, attr):
        return getattr(self._tmp_fo, attr)

# Context managers for Python 2.5 and up, to use with the with statement

class readlock(object):
    """
    Context manager object for acquiring a shared lock on the file,
    so as to read from it.

    Usage:
    with readlock(filename) as (fo, err):
         if err is not None:
             <handle error when opening>
         else:
             <read stuff from fo>
    """
    def __init__(self, filename, mode='rb'):
        self.filename = filename
        if not mode.startswith('r') and mode != 'U':
            raise ValueError("can only lock on reading")
        self.mode = mode
        self._fo = None

    def __enter__(self):
        try:
            self._fo = open(self.filename, mode=self.mode)
        except IOError, err:
            return None, err
        else:
            shared_lock(self._fo)
            return self._fo, None

    def __exit__(self, t, v, tb):
        if self._fo:
            self._fo.close()
        return False

class writelock(object):
    """
    Context manager object for acquiring an exclusive lock on the file,
    so as to write to it.

    Usage:
    with writelock(filename) as (fo, err):
         if err is not None:
             <handle error when opening>
         else:
             <write stuff to fo>
    """
    def __init__(self, filename, mode='w+b'):
        self.filename = filename
        if mode.startswith('r') or mode == 'U':
            raise ValueError('can only lock on writing')
        self.mode = mode
        self._fo = None

    def __enter__(self):
        try:
            self._fo = open(self.filename, mode=self.mode)
        except IOError, err:
            return None, err
        else:
            exclusive_lock(self._fo)
            return self._fo, None

    def __exit__(self, t, v, tb):
        self._fo.close()
        return False

class atomicwritelock(object):
    def __init__(self, filename, keep_backup=True):
        self.filename = filename
        self.keep_backup = keep_backup
        self._fo = None

    def __enter__(self):
        self._fo = WriteLockedFile(self.filename, keep_backup=self.keep_backup)
        return self._fo

    def __exit__(self, t, v, tb):
        if t is None:
            self._fo.commit()
        else:
            self._fo.rollback()
        return False

# Backups

def backup_file(filename):
    shutil.copy(filename, filename+'~')

