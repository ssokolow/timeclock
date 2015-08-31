#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""Wrapper script to make it harder to kill off the bedtime nagger"""

from __future__ import (absolute_import, division, print_function,
                        with_statement, unicode_literals)

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import os, random, signal, string, subprocess, sys  # pylint: disable=W0402
import logging
from setproctitle import setproctitle  # pylint: disable=E0611

try:
    import pygtk
    pygtk.require("2.0")
except ImportError:
    pass

import gtk

log = logging.getLogger(__name__)

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
            log.debug("SIGCHLD -> OSError")
            pass  # We don't want to die if SIGCHLD was for process exit
        else:
            log.warning("Vetoed possible SIGSTOP on timeclock")

def main():
    """The main entry point, compatible with setuptools entry points."""
    from argparse import ArgumentParser
    parser = ArgumentParser(usage="%(prog)s [options]",
            description=__doc__.replace('\r\n', '\n').split('\n--snip--\n')[0])
    parser.add_argument('-v', '--verbose', action="count", dest="verbose",
        default=2, help="Increase the verbosity. Use twice for extra effect")
    parser.add_argument('-q', '--quiet', action="count", dest="quiet",
        default=0, help="Decrease the verbosity. Use twice for extra effect")
    # Reminder: %(default)s can be used in help strings.

    args = parser.parse_args()

    # Set up clean logging to stderr
    log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                  logging.INFO, logging.DEBUG]
    args.verbose = min(args.verbose - args.quiet, len(log_levels) - 1)
    args.verbose = max(args.verbose, 0)
    logging.basicConfig(level=log_levels[args.verbose],
                        format='%(levelname)s: %(message)s')

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
        log.debug("Child exited.")

        # Make sure we'll die on logout or closing Xephyr when testing
        gtk.main_iteration(block=False)  # pylint: disable=no-member
        log.debug("GTK mainloop exited.")

if __name__ == '__main__':
    main()

# vim: set sw=4 sts=4 expandtab :
