#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.

@todo: Planned improvements:
 - Clicking the preferences button while the dialog is shown should do nothing.
 - Rework the design to minimize dependence on GTK+ (in case I switch to Qt for
   Phonon)
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
__authors__  = ["Stephan Sokolow (deitarion/SSokolow)", "Charlie Nolan (FunnyMan3595)"]
__version__ = "0.2"
__license__ = "GNU GPL 2.0 or later"

# Mode constants.
SLEEP, OVERHEAD, WORK, PLAY = range(4)
MODE_NAMES = ("sleep", "overhead", "work", "play")

default_modes = {
    OVERHEAD : 3600 * 4,
    WORK : 3600 * 6,
    PLAY : 3600 * 6,
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

CURRENT_SAVE_VERSION = 2
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
                # Load the data, but leave the internal state unchanged in case
                # of corruption.
                loaded = pickle.load(open(SAVE_FILE))
                version = loaded[0]
                if version == CURRENT_SAVE_VERSION:
                    version, total, used = loaded
                elif version == 1:
                    version, total_old, used_old = loaded
                    translate = ["N/A", "btn_overheadMode", "btn_workMode",
                                 "btn_playMode"]
                    total = dict( (translate.index(key), value)
                                  for key, value in total_old.items() )
                    used = dict( (translate.index(key), value)
                                 for key, value in used_old.items() )
                else:
                    raise ValueError("Save file too new!")

                # Sanity checking could go here.

            except Exception, e:
                logging.error("Unable to load save file. Ignoring: %s", e)
            else:
                # File loaded successfully, now we put the data in place.
                self.total = total
                self.used = used
                self.update_progressBars()

        # Connect signals
        dic = { "on_mode_toggled"    : self.playmode_changed,
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
        self.selectedBtn = self.wTree.get_widget('btn_sleepMode')
        self.selectedBtn.mode = SLEEP

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)
        self.selectedBtn.set_property('draw-indicator', False)

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

    def playmode_changed(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget

    def reset_clicked(self, widget):
        """Callback for the reset button"""
        self.used = dict((x, 0) for x in self.used)
        self.update_progressBars()

    def prefs_clicked(self, widget):
        """Callback for the preferences button"""
        for mode in self.total:
            widget_spin =  'spinBtn_%sMode' % MODE_NAMES[mode]
            widget = self.wTree.get_widget(widget_spin)
            widget.set_value(self.total[mode] / 3600.0)
        self.wTree.get_widget('prefsDlg').show()

    def prefs_cancel(self, widget):
        """Callback for cancelling changes the preferences"""
        self.wTree.get_widget('prefsDlg').hide()

    def prefs_commit(self, widget):
        """Callback for OKing changes to the preferences"""
        for mode in self.total:
            widget_spin =  'spinBtn_%sMode' % MODE_NAMES[mode]
            widget = self.wTree.get_widget(widget_spin)
            self.total[mode] = (widget.get_value() * 3600)
        self.update_progressBars()
        self.wTree.get_widget('prefsDlg').hide()

    def tick(self):
        """Once-per-second timeout callback for updating progress bars."""
        mode = self.selectedBtn.mode
        if mode != SLEEP:
            self.used[mode] += (time.time() - self.last_tick)
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
