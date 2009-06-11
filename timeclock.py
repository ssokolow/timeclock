#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@todo: Planned improvements:
 - Remember timer values between runs
 - Add a preferences dialog for configuring timer values
 - Make the Snooze button a proper special case
 - Use optparse
 - Add optional sound effects for timer completion

@todo: Consider:
 - Changing this into a Plasma widget
 - Using PyKDE's bindings to the KDE Notification system
"""

modes = {
    'overheadMode' : 3600 * 4,
        'workMode' : 3600 * 6,
        'playMode' : 3600 * 6,
       'sleepMode' : 3600 * 8
}

SAVE_PATH = None #: @todo: set this

import signal, sys, time
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
                "on_mainWin_destroy" : gtk.main_quit }
        self.wTree.signal_autoconnect(dic)
        gobject.timeout_add(1000, self.tick)

    def _init_widgets(self):
        """All non-signal, non-glade widget initialization."""
        # Set up the data structures
        self.timer_widgets = {}
        self.total = {}
        self.remaining = {}
        for mode in modes:
            widget = self.wTree.get_widget('btn_%s' % mode)
            self.timer_widgets[widget] = self.wTree.get_widget('progress_%s' % mode)
            self.total[widget] = modes[mode]
            self.remaining[widget] = modes[mode]
        self.selectedBtn = self.wTree.get_widget('btn_sleepMode')

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)

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

    def tick(self):
        """Once-per-second timeout callback for updating progress bars."""
        self.remaining[self.selectedBtn] = self.remaining[self.selectedBtn] - (time.time() - self.last_tick)
        self.last_tick = time.time()
        self.update_progressBars()
        return True

    def onExit(self):
        pass #TODO: Save the current timer values to disk.

if __name__ == "__main__":
    app = TimeClock()

    # Make sure that ScratchTray saves to disk on exit.
    sys.exitfunc = app.onExit
    signal.signal(signal.SIGTERM, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGHUP, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGQUIT, lambda signum, stack_frame: sys.exit(0))
    signal.signal(signal.SIGINT, lambda signum, stack_frame: sys.exit(0))

    try:
        gtk.main()
    except KeyboardInterrupt:
        sys.exit(0)
