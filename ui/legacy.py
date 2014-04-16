"""
@todo: Rewrite this to remove the Glade dependency and support custom sets
       of meters like the compact UI.
"""

import os

import gtk
import gtk.glade

SELF_DIR = os.path.dirname(os.path.realpath(__file__))

class TimeClock(object):
    selectedBtn = None

    def __init__(self, model):

        #Set the Glade file
        self.mTree = gtk.glade.XML(os.path.join(SELF_DIR, "main_large.glade"))
        self.pTree = gtk.glade.XML(os.path.join(SELF_DIR, "preferences.glade"))

        self.model = model
        self._init_widgets()

        #FIXME: Update interaction on load is getting iffy.
        self.model.connect('updated', self.update_progressBars)
        self.model.connect('mode-changed', self.mode_changed)
        self.saved_state = {}

        # Connect signals
        mDic = {"on_mode_toggled": self.btn_toggled,
                "on_reset_clicked": self.cb_reset,
                "on_mainWin_destroy": gtk.main_quit,
                "on_prefs_clicked": self.prefs_clicked}
        pDic = {"on_prefs_commit": self.prefs_commit,
                "on_prefs_cancel": self.prefs_cancel}
        self.mTree.signal_autoconnect(mDic)
        self.pTree.signal_autoconnect(pDic)

        # -- Restore saved window state when possible --

        # Because window-state-event is broken on many WMs, default to sticky,
        # on top as a most likely default for users. (TODO: Preferences toggle)
        self.win = self.mTree.get_widget('mainWin')
        self.win.set_keep_above(True)
        self.win.stick()

        # Restore the saved window state if present
        position = self.saved_state.get('position', None)
        if position is not None:
            self.win.move(*position)
        decorated = self.saved_state.get('decorated', None)
        if decorated is not None:
            self.win.set_decorated(decorated)

    def _init_widgets(self):
        """All non-signal, non-glade widget initialization."""
        # Set up the data structures
        self.timer_widgets = {}
        for mode in self.model.timers:
            widget = self.mTree.get_widget('btn_%sMode' % mode.name.lower())
            widget.mode = mode.name
            self.timer_widgets[widget] = \
                self.mTree.get_widget('progress_%sMode' % mode.name.lower())
        sleepBtn = self.mTree.get_widget('btn_sleepMode')
        sleepBtn.mode = None

        mode_name = self.model.selected.name.lower()
        if mode_name.lower() == 'asleep':
            mode_name == 'sleep'
        self.selectedBtn = self.mTree.get_widget('btn_%sMode' % mode_name)
        self.selectedBtn.set_active(True)

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)
        sleepBtn.set_property('draw-indicator', False)

    def cb_reset(self, widget):
        #TODO: Look into how to get MainWin via parent-lookup calls so this
        # can be destroyed with its parent.
        confirm = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Reset all timers?\n"
                "Warning: This operation cannot be undone.")
        if confirm.run() == gtk.RESPONSE_OK:
            self.model.reset()
        confirm.destroy()

    def update_progressBars(self, model=None, mode=None, delta=None):
        """Common code used for initializing and updating the progress bars.

        :todo: Actually use the values passed in by the emit() call.
        """
        for widget in self.timer_widgets:
            mode = [x for x in self.model.timers if x.name == widget.mode][0]
            pbar = self.timer_widgets[widget]
            remaining = round(mode.remaining())
            if pbar:
                pbar.set_text(str(mode))
                pbar.set_fraction(max(float(remaining) / mode.total, 0))

    def btn_toggled(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget
            self.model.selected = widget.mode

    def mode_changed(self, model, mode):
        mode = mode.name
        btn = self.mTree.get_widget('btn_%sMode' % mode.lower())
        if btn and not btn.get_active():
            btn.set_active(True)

    def prefs_clicked(self, widget):
        """Callback for the preferences button"""
        # Set the spin widgets to the current settings.
        for mode in self.model.timers:
            widget_spin = 'spinBtn_%sMode' % mode.name.lower()
            widget = self.pTree.get_widget(widget_spin)
            widget.set_value(mode.total / 3600.0)

        # Set the notify option to the current value, disable and explain if
        # pynotify is not installed.
        notify_box = self.pTree.get_widget('checkbutton_notify')
        notify_box.set_active(self.model.notify)
        notify_box.set_sensitive(True)
        notify_box.set_label("display notifications")

        self.pTree.get_widget('prefsDlg').show()

    def prefs_cancel(self, widget):
        """Callback for cancelling changes the preferences"""
        self.pTree.get_widget('prefsDlg').hide()

    def prefs_commit(self, widget):
        """Callback for OKing changes to the preferences"""
        # Update the time settings for each mode.
        for mode in self.model.timers:
            widget_spin = 'spinBtn_%sMode' % mode.name.lower()
            widget = self.pTree.get_widget(widget_spin)
            mode.total = (widget.get_value() * 3600)

        notify_box = self.pTree.get_widget('checkbutton_notify')
        self.model.notify = notify_box.get_active()

        # Remaining cleanup.
        self.update_progressBars()
        self.pTree.get_widget('prefsDlg').hide()
