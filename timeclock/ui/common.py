"""Stuff common to both the legacy and compact UIs."""

from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import gtk

from .util import get_icon_path

class ModeWidgetMixin(object):
    """Common boilerplate for implementing timer display widgets"""
    mode = None      # The mode object from the Timeclock model
    button = None    # The gtk.RadioButton to be updated
    progress = None  # The gtk.ProgressBar if applicable

    def _init_children(self):
        """Common __init__ code which needs flexibility in when it's called"""
        if self.progress:
            self.progress.set_fraction(1.0)

        self.button.set_mode(False)
        self.cb_update_label(self.mode)
        self.mode.connect('updated', self.cb_update_label)

    def cb_mode_changed(self, model, mode):
        """Callback for applying external state updates to toggle buttons"""
        if mode == self.mode and not self.button.get_active():
            self.button.set_active(True)

    def cb_update_label(self, mode):
        """Callback for updating the progress bar state"""
        if self.progress:
            self.progress.set_text(self.progress_label(mode))
            self.progress.set_fraction(
                    max(float(mode.remaining()) / mode.total, 0))

    # pylint: disable=no-self-use
    def progress_label(self, mode):
        """Overridable formatter for progress bar text"""
        return mode.remaining_str()

class MainWinMixin(object):
    """Common boilerplate for implementing the main window"""
    model = None    # The top-level Timeclock model object

    def _init_after(self):
        """Common code which needs to be called at the B{end} of __init___"""
        self.set_icon_from_file(get_icon_path(64))

        # Because window-state-event is broken on many WMs, default to sticky,
        # on top as a most likely default for users. (TODO: Preferences toggle)
        self.set_keep_above(True)
        self.stick()

        self.model.connect('updated', self.cb_update)
        self.model.connect('mode-changed', self.cb_mode_changed)

        # TODO: Make this behaviour configurable
        self.connect('destroy', gtk.main_quit)

        self.cb_update(self.model)

    def cb_btn_toggled(self, button, mode_widget):
        """Callback for clicking the timer-selection radio buttons"""
        if button.get_active() and not self.model.selected == mode_widget.mode:
            self.model.selected = mode_widget.mode

    def cb_mode_changed(self, model, mode):
        """Callback for setting external state on non-button mode indicators"""
        self.cb_update(model)

    def cb_reset(self, widget, model):
        """Handler for user requests to reset the timeclock countdowns"""
        confirm = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Reset all timers?\n"
                "Warning: This operation cannot be undone.")

        # Workaround for the dialog showing up beneath MainWin because of
        # _init_after's set_keep_above(True) call.
        confirm.set_keep_above(True)

        if confirm.run() == gtk.RESPONSE_OK:
            self.model.reset()
        confirm.destroy()

    def cb_update(self, model):
        """Callback for handling general status updates"""
        self.set_title(str(model.selected))
