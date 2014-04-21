import os, sys, tempfile

class SingleInstance:
    """Source: http://stackoverflow.com/a/1265445/435253"""
    def __init__(self, useronly=True, lockfile=None, lockname=None):
        """
        :param useronly: Allow one instance per user rather than one instance
            overall. (On Windows, this is always True)
        :param lockfile: Specify an explicit path for the lockfile.
        :param lockname: Specify a filename to be used for the lockfile when
            ``lockfile`` is ``None``. The usual location selection algorithms
            and ``.lock`` extension will apply.

        :note: ``lockname`` assumes it is being given a valid filename.
        """
        self.platform = sys.platform  # Avoid an AttributeError in __del__

        if lockfile:
            self.lockfile = lockfile
        else:
            if lockname:
                fname = lockname + '.lock'
            else:
                fname = os.path.basename(__file__) + '.lock'
            if self.platform == 'win32' or not useronly:
                # According to TechNet, TEMP/TMP are already user-scoped.
                self.lockfile = os.path.join(tempfile.gettempdir(), fname)
            else:
                base = os.environ.get('XDG_CACHE_HOME',
                        os.path.expanduser('~/.cache'))
                self.lockfile = os.path.join(base, fname)

                if not os.path.exists(base):
                    os.makedirs(base)

        self.lockfile = os.path.normpath(os.path.normcase(self.lockfile))

        if self.platform == 'win32':  # TODO: What for Win64? os.name == 'nt'?
            try:
                # file already exists, we try to remove
                # (in case previous execution was interrupted)
                if os.path.exists(self.lockfile):
                    os.unlink(self.lockfile)
                self.fd = os.open(self.lockfile,
                        os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except OSError, err:
                if err.errno == 13:
                    print "Another instance is already running, quitting."
                    sys.exit(-1)
                print err.errno
                raise
        else:  # non Windows
            import fcntl
            self.fobj = open(self.lockfile, 'w')
            try:
                fcntl.lockf(self.fobj, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                print "Another instance is already running, quitting."
                sys.exit(-1)

    def __del__(self):
        if self.platform == 'win32':
            if hasattr(self, 'fd'):
                os.close(self.fd)
                os.unlink(self.lockfile)
