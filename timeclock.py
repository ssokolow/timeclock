#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.
See http://ssokolow.github.com/timeclock/ for a screenshot.

@todo: Planned improvements:
 - Clicking the preferences button while the dialog is shown shouldn't reset the
   unsaved preference changes.
 - Rework single-instance exclusion to ensure it's per-user. (Scope it the same
   as the DB)
 - Extend the single-instance system to use D-Bus if available to raise/focus the
   existing instance if one is already running.
 - Figure out some intuitive, non-distracting way to allow the user to make
   corrections. (eg. if you forget to set the timer to leisure before going AFK)
 - Should I offer preferences options for remembering window position and things
   like "always on top" and "on all desktops"?
 - Have the system complain if overhead + work + leisure + sleep (8 hours) > 24
   and enforce minimums of 1 hour for leisure and overhead.
 - Rework the design to minimize dependence on GTK+ (in case I switch to Qt for
   Phonon)
 - Report PyGTK's uncatchable xkill response on the bug tracker.

@todo: Notification TODO:
 - Provide a fallback for when libnotify notifications are unavailable.
   (eg. Windows and Slax LiveCD/LiveUSB desktops)
 - Offer to turn the timer text a user-specified color (default: red) when it
   goes into negative values.
 - Finish the preferences page.
 - Add optional sound effects for timer completion using gst-python or PyGame:
   - http://mail.python.org/pipermail/python-list/2006-October/582445.html
   - http://www.jonobacon.org/2006/08/28/getting-started-with-gstreamer-with-python/
 - Set up a callback for timer exhaustion.

@todo: Consider:
 - Changing this into a Plasma widget (Without dropping PyGTK support)
 - Using PyKDE's bindings to the KDE Notification system (for the Plasma widget)

@todo: Publish this on listing sites:
 - http://gtk-apps.org/
 - http://pypi.python.org/pypi

@newfield appname: Application Name
"""

__appname__ = "The Procrastinator's Timeclock"
__authors__  = ["Stephan Sokolow (deitarion/SSokolow)", "Charlie Nolan (FunnyMan3595)"]
__version__ = "0.2"
__license__ = "GNU GPL 2.0 or later"

# Mode constants.
SLEEP, OVERHEAD, WORK, LEISURE = range(4)
MODE_NAMES = ("sleep", "overhead", "work", "leisure")

default_modes = {
    OVERHEAD : int(3600 * 3.5),
    WORK : 3600 * 6,
    LEISURE : int(3600 * 5.5),
}

import errno, logging, os, signal, sys, tempfile, time, pickle

SELF_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        raise SystemExit("Aborting: %s exists but is not a directory!"
                               % DATA_DIR)
SAVE_FILE = os.path.join(DATA_DIR, "timeclock.sav")
SAVE_INTERVAL = 60 * 5  # 5 Minutes
file_exists = os.path.isfile

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    import pygtk
    pygtk.require("2.0")
except:
    pass

import gtk, gobject
import gtk.glade
import gtkexcepthook

try:
    import pynotify
    from xml.sax.saxutils import escape as xmlescape
except ImportError:
    have_pynotify = False
    notify_exhaustion = lambda timer_name: None
else:
    have_pynotify = True
    pynotify.init(__appname__)

    # Make the notifications in advance,
    notifications = {}
    for mode in default_modes:
        mode_name = MODE_NAMES[mode]
        notification = pynotify.Notification(
            "%s Time Exhausted" % mode_name.title(),
            "You have used up your alotted time for %s" % xmlescape(mode_name.lower()),
            os.path.join(SELF_DIR, "icons", "timeclock_48x48.png"))
        notification.set_urgency(pynotify.URGENCY_NORMAL)
        notification.set_timeout(pynotify.EXPIRES_NEVER)
        notification.last_shown = 0
        notifications[mode] = notification

    def notify_exhaustion(mode):
        """Display a libnotify notification that the given timer has expired."""
        notification = notifications[mode]
        now = time.time()
        if notification.last_shown + 900 < now:
            notification.last_shown = now
            notification.show()

class SingleInstance:
    """http://stackoverflow.com/questions/380870/python-single-instance-of-program/1265445#1265445"""
    def __init__(self):
        import sys
        self.lockfile = os.path.normpath(tempfile.gettempdir() + '/' + os.path.basename(__file__) + '.lock')
        if sys.platform == 'win32':
                try:
                        # file already exists, we try to remove (in case previous execution was interrupted)
                        if(os.path.exists(self.lockfile)):
                                os.unlink(self.lockfile)
                        self.fd =  os.open(self.lockfile, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                except OSError, e:
                        if e.errno == 13:
                                print "Another instance is already running, quitting."
                                sys.exit(-1)
                        print e.errno
                        raise
        else: # non Windows
                import fcntl, sys
                self.fp = open(self.lockfile, 'w')
                try:
                        fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                        print "Another instance is already running, quitting."
                        sys.exit(-1)

    def __del__(self):
        if sys.platform == 'win32':
                if hasattr(self, 'fd'):
                        os.close(self.fd)
                        os.unlink(self.lockfile)
me = SingleInstance()

CURRENT_SAVE_VERSION = 3 #: Used for save file versioning
class TimeClock:
    def __init__(self, default_mode="sleep"):
        self.default_mode = default_mode

        #Set the Glade file
        self.gladefile = os.path.join(SELF_DIR, "timeclock.glade")
        self.wTree = gtk.glade.XML(self.gladefile)

        self.last_tick = time.time()
        self.last_save = 0
        self._init_widgets()

        self.notify = True

        # Load the save file, if it exists.
        if file_exists(SAVE_FILE):
            try:
                # Load the data, but leave the internal state unchanged in case
                # of corruption.
                loaded = pickle.load(open(SAVE_FILE))
                version = loaded[0]
                if version == CURRENT_SAVE_VERSION:
                    version, total, used, notify = loaded
                elif version == 2:
                    version, total, used = loaded
                    notify = True
                elif version == 1:
                    version, total_old, used_old = loaded
                    translate = ["N/A", "btn_overheadMode", "btn_workMode",
                                 "btn_playMode"]
                    total = dict( (translate.index(key), value)
                                  for key, value in total_old.items() )
                    used = dict( (translate.index(key), value)
                                 for key, value in used_old.items() )
                    notify = True
                else:
                    raise ValueError("Save file too new!")

                # Sanity checking could go here.

            except Exception, e:
                logging.error("Unable to load save file. Ignoring: %s", e)
            else:
                # File loaded successfully, now we put the data in place.
                self.total = total
                self.used = used
                self.notify = notify
                self.update_progressBars()

        # Connect signals
        dic = { "on_mode_toggled"    : self.mode_changed,
                "on_reset_clicked"   : self.reset_clicked,
                "on_prefs_clicked"   : self.prefs_clicked,
                "on_prefs_commit"    : self.prefs_commit,
                "on_prefs_cancel"    : self.prefs_cancel,
                "on_mainWin_destroy" : gtk.main_quit }
        self.wTree.signal_autoconnect(dic)
        gobject.timeout_add(1000, self.tick)

    def _init_widgets(self):
        """All non-signal, non-glade widget initialization."""
        # Set up the data structures
        self.timer_widgets = {}
        self.total, self.used = {}, {}
        for mode in default_modes:
            widget = self.wTree.get_widget('btn_%sMode' % MODE_NAMES[mode])
            widget.mode = mode
            self.timer_widgets[widget] = \
                self.wTree.get_widget('progress_%sMode' % MODE_NAMES[mode])
            self.total[mode] = default_modes[mode]
            self.used[mode] = 0
        sleepBtn = self.wTree.get_widget('btn_sleepMode')
        sleepBtn.mode = SLEEP

        self.selectedBtn = self.wTree.get_widget('btn_%sMode' % self.default_mode)
        self.selectedBtn.set_active(True)

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)
        sleepBtn.set_property('draw-indicator', False)

    def update_progressBars(self):
        """Common code used for initializing and updating the progress bars."""
        for widget in self.timer_widgets:
            pbar = self.timer_widgets[widget]
            total, val = self.total[widget.mode], self.used[widget.mode]
            remaining = round(total - val)
            if pbar:
                if remaining >= 0:
                    pbar.set_text(time.strftime('%H:%M:%S', time.gmtime(remaining)))
                else:
                    pbar.set_text(time.strftime('-%H:%M:%S', time.gmtime(abs(remaining))))
                pbar.set_fraction(max(float(remaining) / self.total[widget.mode], 0))

    def mode_changed(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget

        if self.selectedBtn.mode == SLEEP:
            self.doSave()

    def reset_clicked(self, widget):
        """Callback for the reset button"""
        self.used = dict((x, 0) for x in self.used)
        self.wTree.get_widget('btn_%sMode' % MODE_NAMES[SLEEP]).set_active(True)
        self.update_progressBars()

    def prefs_clicked(self, widget):
        """Callback for the preferences button"""
        # Set the spin widgets to the current settings.
        for mode in self.total:
            widget_spin =  'spinBtn_%sMode' % MODE_NAMES[mode]
            widget = self.wTree.get_widget(widget_spin)
            widget.set_value(self.total[mode] / 3600.0)

        # Set the notify option to the current value, disable and explain if
        # pynotify is not installed.
        notify_box = self.wTree.get_widget('checkbutton_notify')
        notify_box.set_active(self.notify)
        if have_pynotify:
            notify_box.set_sensitive(True)
            notify_box.set_label("display notifications")
        else:
            notify_box.set_sensitive(False)
            notify_box.set_label("display notifications (Requires pynotify)")

        self.wTree.get_widget('prefsDlg').show()

    def prefs_cancel(self, widget):
        """Callback for cancelling changes the preferences"""
        self.wTree.get_widget('prefsDlg').hide()

    def prefs_commit(self, widget):
        """Callback for OKing changes to the preferences"""
        # Update the time settings for each mode.
        for mode in self.total:
            widget_spin =  'spinBtn_%sMode' % MODE_NAMES[mode]
            widget = self.wTree.get_widget(widget_spin)
            self.total[mode] = (widget.get_value() * 3600)

        notify_box = self.wTree.get_widget('checkbutton_notify')
        self.notify = notify_box.get_active()

        # Remaining cleanup.
        self.update_progressBars()
        self.wTree.get_widget('prefsDlg').hide()

    def tick(self):
        """Once-per-second timeout callback for updating progress bars."""
        mode = self.selectedBtn.mode
        now = time.time()
        if mode != SLEEP:
            self.used[mode] += (now - self.last_tick)
            self.update_progressBars()

            if self.used[mode] >= self.total[mode] and self.notify:
                notify_exhaustion(mode)

            if now >= (self.last_save + SAVE_INTERVAL):
                self.doSave()

        self.last_tick = now

        return True

    def doSave(self):
        """Exit/Timeout handler for the app. Gets called every five minutes and
        on every type of clean exit except xkill. (PyGTK doesn't let you)

        Saves the current timer values to disk."""
        pickle.dump( (CURRENT_SAVE_VERSION, self.total, self.used, self.notify),
                     open(SAVE_FILE, "w") )
        self.last_save = time.time()
        return True

def main():
    from optparse import OptionParser
    parser = OptionParser(version="%%prog v%s" % __version__)
    #parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
    #    default=False, help="Increase verbosity")
    parser.add_option('-m', '--initial-mode',
                      action="store", dest="mode", default="sleep",
                      metavar="MODE", help="start in MODE. (Use 'help' for a list)")

    opts, args = parser.parse_args()
    if opts.mode == 'help':
        print "Valid mode names are: %s" % ', '.join(MODE_NAMES)
        parser.exit(0)
    elif (opts.mode not in MODE_NAMES):
        print "Mode '%s' not recognized, defaulting to sleep." % opts.mode
        opts.mode = "sleep"
    app = TimeClock(default_mode=opts.mode)

    # Make sure that state is saved to disk on exit.
    sys.exitfunc = app.doSave
    signal.signal(signal.SIGTERM, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGQUIT, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, stack_frame: sys.exit(0))

    try:
        gtk.main()
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()
