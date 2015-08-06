#!/usr/bin/env python
"""Wrapper script to make it harder to kill off the bedtime nagger"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import os, random, signal, string, subprocess, sys  # pylint: disable=W0402
from setproctitle import setproctitle  # pylint: disable=E0611

try:
    import pygtk
    pygtk.require("2.0")
except ImportError:
    pass

import gtk

def get_random_proctitle():
    """Return a 16-character alphanumeric string

    Sources:
        - http://stackoverflow.com/a/2257449/435253
        - http://stackoverflow.com/a/23534499/435253
    """
    return ''.join(random.SystemRandom().choice(
        string.ascii_letters + string.digits) for _ in range(16))

child_pid = None
def cont_child(signum, frame): # pylint: disable=unused-argument
    """Callback for handling SIGCHLD"""
    if child_pid:
        try:
            os.kill(child_pid, signal.SIGCONT)
        except OSError:
            pass  # We don't want to die if SIGCHLD was for process exit
        else:
            print("Vetoed possible SIGSTOP on timeclock")


if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__))

    # Ignore as many normally fatal signals as possible
    for signame in ("SIGABRT", "SIGALRM", "SIGVTALRM", "SIGHUP", "SIGINT",
                    "SIGPROF", "SIGQUIT", "SIGTERM", "SIGTSTP", "SIGTRAP",
                    "SIGUSR1", "SIGUSR2"):
        sigconst = getattr(signal, signame, None)
        if sigconst:
            signal.signal(sigconst, signal.SIG_IGN)

    # Use SIGCHLD to catch and reverse SIGSTOP on timeclock
    signal.signal(signal.SIGCHLD, cont_child)

    while True:
        # Make us immune to killing via .bash_history/.zhistory
        setproctitle(get_random_proctitle())

        # Actually launch timeclock
        tcproc = subprocess.Popen(["./timeclock.py"] + sys.argv[1:])
        child_pid = tcproc.pid
        tcproc.wait()

        # Make sure we'll die on logout or closing Xephyr when testing
        gtk.main_iteration()  # pylint: disable=no-member
