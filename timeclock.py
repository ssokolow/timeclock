#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.

@todo: Planned improvements:
 - Remember timer values between runs
 - Finish building the preferences dialog, make it functional, and hook it up.
 - Add optional sound effects for timer completion
 - Have the system complain if overhead + work + play + sleep (8 hours) > 24
   and enforce minimums of 1 hour for leisure and overhead.

@todo: Consider:
 - Changing this into a Plasma widget
 - Using PyKDE's bindings to the KDE Notification system
 - Report PyGTK's uncatchable xkill response on the bug tracker.
"""

__appname__ = "The Procrastinator's Timeclock"
__author__  = "Stephan Sokolow (deitarion/SSokolow)"
__version__ = "0.1"
__license__ = "GNU GPL 2.0 or later"

default_modes = {
    'overheadMode' : 3600 * 4,
        'workMode' : 3600 * 6,
        'playMode' : 3600 * 6,
}

import logging, os, signal, sys, time
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
try:
    import pygtk
    pygtk.require("2.0")
except:
    pass

try:
    import gtk, gobject
    import gtk.glade
except:
    sys.exit(1)

DATA_DIR = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))

class TimeClock:
    def __init__(self):
        #Set the Glade file
        self.gladefile = "timeclock.glade"
        self.wTree = gtk.glade.XML(self.gladefile)

        self.last_tick = time.time()
        self._init_widgets()
        #TODO: If present, restore the timer save file.

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
        self.total, self.remaining = {}, {}
        for mode in default_modes:
            widget = self.wTree.get_widget('btn_%s' % mode)
            self.timer_widgets[widget] = self.wTree.get_widget('progress_%s' % mode)
            self.total[widget] = default_modes[mode]
            self.remaining[widget] = default_modes[mode]
        self.selectedBtn = self.wTree.get_widget('btn_sleepMode')

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)
        self.selectedBtn.set_property('draw-indicator', False)

    def update_progressBars(self):
        """Common code used for initializing and updating the progress bars."""
        for widget in self.timer_widgets:
            pbar, val = self.timer_widgets[widget], self.remaining[widget]
            if pbar:
                if val >= 0:
                    pbar.set_text(time.strftime('%H:%M:%S', time.gmtime(val)))
                else:
                    pbar.set_text(time.strftime('-%H:%M:%S', time.gmtime(abs(val))))
                pbar.set_fraction(max(float(val) / self.total[widget], 0))

    def playmode_changed(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget

    def reset_clicked(self, widget):
        """Callback for the reset button"""
        self.remaining = self.total.copy()
        self.update_progressBars()

    def prefs_clicked(self, widget):
        """Callback for the preferences button"""
        logging.error("TODO: Implement this")

    def tick(self):
        """Once-per-second timeout callback for updating progress bars."""
        if self.selectedBtn.get_name() != 'btn_sleepMode':
            self.remaining[self.selectedBtn] -= (time.time() - self.last_tick)
            self.last_tick = time.time()
            self.update_progressBars()
        return True

    def onExit(self):
        """Exit handler for the app. Gets called on everything but xkill.
        @todo: Save the current timer values to disk."""
        logging.info("TODO: Shutdown handler")

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
