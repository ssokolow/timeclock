#!/usr/bin/env python
"""Wrapper script to make it harder to kill off the bedtime nagger"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "MIT"

import os, random, string, subprocess, sys  # pylint: disable=deprecated-module
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

if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__))

    while True:
        # Make us immune to killing via .bash_history/.zhistory
        setproctitle(get_random_proctitle())

        # Actually launch timeclock
        subprocess.call(["./timeclock.py"] + sys.argv[1:])

        # Make sure we'll die on logout or closing Xephyr when testing
        gtk.main_iteration()
