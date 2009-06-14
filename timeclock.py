#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.

@todo: Planned improvements:
 - Rework the design to minimize dependence on GTK+ (in case I switch to Qt for
   Phonon)
 - Make the preferences dialog functional and hook up the button for it.
 - Have the system complain if overhead + work + play + sleep (8 hours) > 24
   and enforce minimums of 1 hour for leisure and overhead.
 - Report PyGTK's uncatchable xkill response on the bug tracker.

@todo: Notification TODO:
 - Set up a callback for timer exhaustion.
 - Build the preferences page.
 - Hook up notify_exhaustion with all appropriate conditionals.
 - Offer to turn the timer text a user-specified color (default: red) when it
   goes into negative values.
 - Add optional sound effects for timer completion using gst-python or PyGame:
   - http://mail.python.org/pipermail/python-list/2006-October/582445.html
   - http://www.jonobacon.org/2006/08/28/getting-started-with-gstreamer-with-python/

@todo: Consider:
 - Changing this into a Plasma widget
 - Using PyKDE's bindings to the KDE Notification system
"""

__appname__ = "The Procrastinator's Timeclock"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.2"
__license__ = "GNU GPL 2.0 or later"

default_modes = {
    'overheadMode' : 3600 * 4,
        'workMode' : 3600 * 6,
        'playMode' : 3600 * 6,
}

import logging, os, signal, sys, time, pickle

DATA_DIR = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        raise SystemExit("Aborting: %s exists but is not a directory!"
                               % DATA_DIR)
SAVE_FILE = os.path.join(DATA_DIR, "timeclock.sav")
file_exists = os.path.isfile

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    import pygtk
    pygtk.require("2.0")
except:
    pass

try:
    import gtk, gobject
    import gtk.glade
except ImportError:
    sys.exit(1)

try:
    import pynotify
    pynotify.init(__appname___)
    def notify_exhaustion(timer_name):
        notification = pynotify.Notification(
            "%s Time Exhausted" % timer_name.title(),
            "You have used up your alotted time for %s" % timer_name.lower(),
            "dialog-warning")
        notification.set_urgency(pynotify.URGENCY_NORMAL)
        notification.set_timeout(pynotify.EXPIRES_NEVER)
        notification.show()
except:
    notify_exhaustion = None

CURRENT_SAVE_VERSION = 1
class TimeClock:
    def __init__(self):
        #Set the Glade file
        self.gladefile = "timeclock.glade"
        self.wTree = gtk.glade.XML(self.gladefile)

        self.last_tick = time.time()
        self._init_widgets()

        # Load the save file, if it exists.
        if file_exists(SAVE_FILE):
            try:
                loaded = pickle.load(open(SAVE_FILE))
                version = loaded[0]
                if version == CURRENT_SAVE_VERSION:
                    version, self.total, self.used = loaded
            except Exception:
                logging.error("Unable to load save file. Ignoring: %s", SAVE_FILE)
            else:
                self.update_progressBars()

        # Connect signals
        dic = { "on_mode_toggled"    : self.playmode_changed,
                "on_reset_clicked"   : self.reset_clicked,
                "on_prefs_clicked"   : self.prefs_clicked,
                "on_mainWin_destroy" : gtk.main_quit }
        self.wTree.signal_autoconnect(dic)
        gobject.timeout_add(1000, self.tick)

    def _init_widgets(self):
        """All non-signal, non-glade widget initialization."""
        # Set up the data structures
        self.timer_widgets = {}
        self.total, self.used = {}, {}
        for mode in default_modes:
            widget = self.wTree.get_widget('btn_%s' % mode)
            self.timer_widgets[widget] = self.wTree.get_widget('progress_%s' % mode)
            widget_name = widget.get_name()
            self.total[widget_name] = default_modes[mode]
            self.used[widget_name] = 0
        self.selectedBtn = self.wTree.get_widget('btn_sleepMode')

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)
        self.selectedBtn.set_property('draw-indicator', False)

    def update_progressBars(self):
        """Common code used for initializing and updating the progress bars."""
        for widget in self.timer_widgets:
            pbar = self.timer_widgets[widget]
            widget_name = widget.get_name()
            total, val = self.total[widget_name], self.used[widget_name]
            remaining = round(total - val)
            if pbar:
                if remaining >= 0:
                    pbar.set_text(time.strftime('%H:%M:%S', time.gmtime(remaining)))
                else:
                    pbar.set_text(time.strftime('-%H:%M:%S', time.gmtime(abs(remaining))))
                pbar.set_fraction(max(float(remaining) / self.total[widget_name], 0))

    def playmode_changed(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget

    def reset_clicked(self, widget):
        """Callback for the reset button"""
        self.used = dict((x.get_name(), 0) for x in self.used)
        self.update_progressBars()

    def prefs_clicked(self, widget):
        """Callback for the preferences button"""
        logging.error("TODO: Implement this")

    def tick(self):
        """Once-per-second timeout callback for updating progress bars."""
        selected_name = self.selectedBtn.get_name()
        if selected_name != 'btn_sleepMode':
            self.used[selected_name] += (time.time() - self.last_tick)
            self.update_progressBars()
        self.last_tick = time.time()
        return True

    def onExit(self):
        """Exit handler for the app. Gets called on everything but xkill.

        Saves the current timer values to disk."""
        pickle.dump( (CURRENT_SAVE_VERSION, self.total, self.used),
                     open(SAVE_FILE, "w") )

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(version="%%prog v%s" % __version__)
    #parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
    #    default=False, help="Increase verbosity")

    opts, args = parser.parse_args()
    app = TimeClock()

    # Make sure that state is saved to disk on exit.
    sys.exitfunc = app.onExit
    signal.signal(signal.SIGTERM, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGQUIT, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, stack_frame: sys.exit(0))

    try:
        gtk.main()
    except KeyboardInterrupt:
        sys.exit(0)
