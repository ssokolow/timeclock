"""Stuff common to both the legacy and compact UIs."""

import gtk

from util import get_icon_path

class ModeWidgetMixin(object):
    mode = None      # The mode object from the Timeclock model
    button = None    # The gtk.RadioButton to be updated
    progress = None  # The gtk.ProgressBar if applicable
    progress_label = lambda _, mode: mode.remaining_str()

    def _init_children(self):
        if self.progress:
            self.progress.set_fraction(1.0)

        self.button.set_mode(False)
        self.cb_update_label(self.mode)
        self.mode.connect('updated', self.cb_update_label)

    def cb_mode_changed(self, model, mode):
        if mode == self.mode and not self.button.get_active():
            self.button.set_active(True)

    def cb_update_label(self, mode):
        if self.progress:
            self.progress.set_text(self.progress_label(mode))
            self.progress.set_fraction(
                    max(float(mode.remaining()) / mode.total, 0))

class MainWinMixin(object):
    model = None    # The top-level Timeclock model object

    def _init_after(self):
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

    #TODO: Normalize callback naming
    def cb_btn_toggled(self, button, mode_widget):
        """Callback for clicking the timer-selection radio buttons"""
        if button.get_active() and not self.model.selected == mode_widget.mode:
            self.model.selected = mode_widget.mode

    def cb_mode_changed(self, model, mode):
        self.cb_update(model)

    def cb_reset(self, widget, model):
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
        self.set_title(str(model.selected))
