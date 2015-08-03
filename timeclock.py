#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.
See http://ssokolow.github.com/timeclock/ for a screenshot.

@todo: Update site to reflect PyGTK 2.8 being required for PyCairo.

@todo: Optionally use idle detection to auto-trigger Overhead on wake
 - http://msdn.microsoft.com/en-us/library/ms646302.aspx (pywin32?)
 - http://stackoverflow.com/questions/608710/monitoring-user-idle-time
 - Probably a good idea to write and share a wrapper

@todo: Planned improvements:
 - Amend SingleInstance to show() and/or raise() a provided main window if none
   is found.
 - Look into offering an IdleController mode for people who turn their PCs off.
   - In fact, look into offering generic support for taking into account time
     with the timeclock turned off.
 - Strip out all these super() calls since it's still easy to introduce subtle
   bugs by forgetting to super() to the top of every branch of the hierarchy.
 - Decide whether overflow_to should cascade.
 - Double-check that it still works on Python 2.4.
 - Have the system complain if overhead + work + leisure + sleep (8 hours) > 24
   and enforce minimums of 1 hour for leisure and overhead.
 - Clicking the preferences button while the dialog is shown shouldn't reset
   the unsaved preference changes.
 - Extend the single-instance system to use D-Bus if available to raise/focus
   the existing instance if one is already running.
 - Figure out some intuitive, non-distracting way to allow the user to make
   corrections. (eg. you forgot to set the timer to leisure before going AFK)
 - Report PyGTK's uncatchable xkill response on the bug tracker.
 - Profile timeclock. Something this size shouldn't take 0.6% of an Athon 5000+

@todo: Notification TODO:
 - Offer to turn the timer text a user-specified color (default: red) when it
   goes into negative values.
 - Set up a callback for timer exhaustion.
 - Handle popup notifications more intelligently (eg. Explicitly hide them when
   switching away from an expired timer and explicitly show them when switching
   to one)

@todo: Consider:
 - Look into integrating with http://projecthamster.wordpress.com/

@todo: Publish this on listing sites:
 - http://gtk-apps.org/
 - http://pypi.python.org/pypi

@newfield appname: Application Name
"""

__appname__ = "The Procrastinator's Timeclock"
__authors__ = [
    "Stephan Sokolow (deitarion/SSokolow)",
    "Charlie Nolan (FunnyMan3595)"]
__author__ = ', '.join(__authors__)
__version__ = "0.2.99.0"
__license__ = "GNU GPL 2.0 or later"

default_timers = [
    {
        'class': 'UnlimitedMode',
        'name': 'Asleep',
        'total': int(3600 * 8),
        'used': 0,
    },
    {
        'name': 'Overhead',
        'total': int(3600 * 3.5),
        'used': 0,
        'overflow': 'Leisure'
    },
    {
        'name': 'Work',
        'total': int(3600 * 6.0),
        'used': 0,
    },
    {
        'name': 'Leisure',
        'total': int(3600 * 5.5),
        'used': 0,
    }
]

import logging, os, signal, sys
from datetime import datetime, time, timedelta
from importlib import import_module

log = logging.getLogger(__name__)

#from gi import pygtkcompat
#pygtkcompat.enable()
#pygtkcompat.enable_gtk(version='3.0')

try:
    import pygtk
    pygtk.require("2.0")
except ImportError:
    pass


DEFAULT_UI_LIST = ['compact']
DEFAULT_NOTIFY_LIST = ['audio', 'libnotify', 'osd']

import gtk
import gtk.gdk  # pylint: disable=import-error

# pylint: disable=no-name-in-module
from timeclock.util import gtkexcepthook
from timeclock.util.single_instance import SingleInstance

from timeclock.model import TimerModel  # pylint: disable=no-name-in-module

SELF_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.environ.get('XDG_DATA_HOME',
        os.path.expanduser('~/.local/share'))
SAVE_FILE = os.path.join(DATA_DIR, "timeclock.sav")

if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        raise SystemExit("Aborting: %s exists but is not a directory!"
                         % DATA_DIR)

KNOWN_NOTIFY_MAP = {
        'audio': 'AudioNotifier',
        'libnotify': 'LibNotifyNotifier',
        'osd': 'OSDNaggerNotifier'
}

KNOWN_CONTROLLER_MAP = {
    'timer': 'TimerController',
    'idle': 'IdleController',
    'bedtime_enforcer': 'BedtimeEnforcer',
}

# pylint: disable=no-member
KNOWN_UI_LIST = ['compact', 'legacy']


def main():
    """Main entry point for the application"""
    from optparse import OptionParser
    parser = OptionParser(version="%%prog v%s" % __version__)
    parser.add_option('-m', '--initial-mode', action="store", dest="mode",
                      default="Asleep", metavar="MODE",
                      help="start in MODE. (Use 'help' for a list)")
    parser.add_option('--ui',
                      action="append", dest="interfaces", default=[],
                      type='choice', choices=KNOWN_UI_LIST,
                      metavar="NAME",
                      help="Launch the specified UI instead of the default. "
                      "May be specified multiple times for multiple UIs.")
    parser.add_option('--notifier',
                      action="append", dest="notifiers", default=[],
                      type='choice', choices=KNOWN_NOTIFY_MAP.keys(),
                      metavar="NAME",
                      help="Activate the specified notification method. "
                      "May be specified several times for multiple notifiers.")
    parser.add_option('--develop',
                      action="store_true", dest="develop", default=False,
                      help="Use separate data store and single instance lock"
                      "so a development copy can be launched without "
                      "interfering with normal use")
    parser.add_option('--test',
                      action="store_true", dest="test_mode", default=False,
                      help="Configure Bedtime Enforcer for testing")
    parser.add_option('-v', '--verbose', action="count", dest="verbose",
        default=3, help="Increase the verbosity.")
    parser.add_option('-q', '--quiet', action="count", dest="quiet",
        default=0, help="Decrease the verbosity. Use thrice for extra effect")

    opts, _ = parser.parse_args()

    # Set up clean logging to stderr
    log_levels = [logging.CRITICAL, logging.ERROR, logging.WARNING,
                  logging.INFO, logging.DEBUG]
    opts.verbose = min(opts.verbose - opts.quiet, len(log_levels) - 1)
    opts.verbose = max(opts.verbose, 0)
    logging.basicConfig(level=log_levels[opts.verbose],
                        format='%(levelname)s: %(message)s')

    if opts.develop:
        lockname = __file__ + '.dev'
        savefile = SAVE_FILE + '.dev'
    else:
        lockname, savefile = None, SAVE_FILE

    keepalive = []
    keepalive.append(SingleInstance(lockname=lockname))
    # This two-line definition shuts PyFlakes up about "assigned but not used"
    # Stuff beyond this point only runs if no other instance is already running

    gtkexcepthook.enable()

    # Model
    model = TimerModel(savefile, default_timers, opts.mode)

    if opts.test_mode:
        now = datetime.utcnow()
        model.bedtime_enforcer = {
            'bedtime': time(hour=now.hour, minute=now.minute,
                            second=now.second),
            'sleep_duration': timedelta(seconds=10),
            'snooze_duration': timedelta(seconds=5),
            'update_interval': timedelta(seconds=1)
        }

    if opts.mode == 'help':
        print "Valid mode names are: %s" % ', '.join(model.timers)
        parser.exit(0)
    elif (opts.mode not in [x.name for x in model.timers]):
        default = model.timers[0]
        print ("Mode '%s' not recognized, defaulting to %s." %
            (opts.mode, default.name))
        opts.mode = default

    # TODO: Finish refactoring and deduplicating this loading harness
    def load_module(model, package, name, clsname):
        if not clsname:  # TODO: Instead of catching None here, do it properly.
            log.warn("Failed to resolve module name %s", name)
            return None

        try:
            # TODO: Use https://pypi.python.org/pypi/importlib/ to support
            # Python 2.6 and earlier.
            module = import_module('timeclock.%s.%s' % (package, name))
        except ImportError, err:
            log.warn("Could not initialize %s.%s due to unsatisfied "
                     "dependencies:\n\t%s", package, name, err)
            return None

        cls = getattr(module, clsname, None)
        if not cls:
            log.warn("Could not find class %s.%s.%s", package, name, clsname)
            return None

        try:
            cls(model)
        except Exception, err:
            log.warn("%s.%s failed to initialize:\n\t%s", package, name, err)
        else:
            log.info("Successfully instantiated %s.%s", package, name)

    # Controllers
    for name, clsname in KNOWN_CONTROLLER_MAP.items():
        load_module(model, 'controllers', name, clsname)

    # Notification Views
    if not opts.notifiers:
        opts.notifiers = DEFAULT_NOTIFY_LIST
    for name in opts.notifiers:
        load_module(model, 'notifications', name, KNOWN_NOTIFY_MAP.get(name))

    # UI Views
    if not opts.interfaces:
        opts.interfaces = DEFAULT_UI_LIST
    for name in opts.interfaces:
        load_module(model, 'ui', name, 'MainWin')

    #TODO: Split out the PyNotify parts into a separate view(?) module.
    #TODO: Write up an audio notification view(?) module.
    #TODO: Try adding a "set urgent hint" call on the same interval as these.

    # Save state on exit
    sys.exitfunc = model.save

    def sighandler(signum, stack_frame):
        if not model.suppress_shutdown:
            sys.exit(0)

    # Make sure signals call sys.exitfunc.
    for signame in ("SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT"):
        sigconst = getattr(signal, signame, None)
        if sigconst:
            signal.signal(sigconst, sighandler)

    # Make sure sys.exitfunc gets called on Ctrl+C
    try:
        gtk.main()  # TODO: Find some way to hook a lost X11 connection too.
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()

# vi:ts=4:sts=4:sw=4
