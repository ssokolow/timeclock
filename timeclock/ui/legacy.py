"""
@todo: Rewrite this to remove the Glade dependency and support custom sets
       of meters like the compact UI.
"""

from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import gtk

from .common import ModeWidgetMixin, MainWinMixin

class FiniteModeWidget(gtk.VBox, ModeWidgetMixin):
    """Widget for displaying timers which can run out"""
    def __init__(self, mode, *args, **kwargs):
        super(FiniteModeWidget, self).__init__(*args, **kwargs)

        self.mode = mode
        self.button = gtk.RadioButton(label=mode.name)
        self.progress = gtk.ProgressBar()

        self._init_children()

        self.add(self.progress)
        self.add(self.button)

class InfiniteModeWidget(gtk.RadioButton, ModeWidgetMixin):
    """Widget for displaying timers which cannot run out"""
    def __init__(self, mode, *args, **kwargs):
        super(InfiniteModeWidget, self).__init__(*args, **kwargs)

        self.mode = mode
        self.button = self  # XXX: Is there any potential harm in this?

        self._init_children()
        self.set_label(mode.name)

class MainWin(gtk.Window, MainWinMixin):
    """Compact UI suitable for overlaying on titlebars"""
    def __init__(self, model):
        super(MainWin, self).__init__()

        self.model = model
        self.box = gtk.VBox(spacing=5)
        self.mode_btns = gtk.HBox(spacing=5)
        self.misc_btns = gtk.HBox(spacing=5)

        first_btn = None
        for mode in model.timers:
            if mode.show:  # FIXME: This isn't the property to be switching on
                wid = FiniteModeWidget(mode, spacing=5)
                self.mode_btns.add(wid)
            else:
                wid = InfiniteModeWidget(mode)
                self.misc_btns.add(wid)

            wid.button.connect('toggled', self.cb_btn_toggled, wid)

            if first_btn:
                wid.button.set_group(first_btn)
            else:
                first_btn = wid.button

            model.connect('mode-changed', wid.cb_mode_changed)

        self.prefs_btn = gtk.Button()
        self.prefs_btn.set_image(gtk.image_new_from_stock('gtk-preferences',
                                    gtk.ICON_SIZE_BUTTON))
        self.reset_btn = gtk.Button(label='Reset')

        #  TODO: prefs
        self.reset_btn.connect('clicked', self.cb_reset, self.model)

        self.misc_btns.pack_start(self.prefs_btn, expand=False)
        self.misc_btns.add(self.reset_btn)

        self.box.pack_start(self.mode_btns)
        self.box.pack_start(gtk.HSeparator(), expand=False, padding=5)
        self.box.pack_start(self.misc_btns)

        self.box.set_border_width(5)
        self.add(self.box)

        self._init_after()
        self.show_all()

#class TimeClock(object):
#    selectedBtn = None
#
#    def __init__(self, model):
#
#        self.saved_state = {}
#
#        pDic = {"on_prefs_commit": self.prefs_commit,
#                "on_prefs_cancel": self.prefs_cancel}
#        self.pTree.signal_autoconnect(pDic)
#
#        # -- Restore saved window state when possible --
#
#        # Restore the saved window state if present
#        position = self.saved_state.get('position', None)
#        if position is not None:
#            self.win.move(*position)
#        decorated = self.saved_state.get('decorated', None)
#        if decorated is not None:
#            self.win.set_decorated(decorated)
#
#    def prefs_clicked(self, widget):
#        """Callback for the preferences button"""
#        # Set the spin widgets to the current settings.
#        for mode in self.model.timers:
#            widget_spin = 'spinBtn_%sMode' % mode.name.lower()
#            widget = self.pTree.get_widget(widget_spin)
#            widget.set_value(mode.total / 3600.0)
#
#        # Set the notify option to the current value, disable and explain if
#        # pynotify is not installed.
#        notify_box = self.pTree.get_widget('checkbutton_notify')
#        notify_box.set_active(self.model.notify)
#        notify_box.set_sensitive(True)
#        notify_box.set_label("display notifications")
#
#        self.pTree.get_widget('prefsDlg').show()
#
#    def prefs_cancel(self, widget):
#        """Callback for cancelling changes the preferences"""
#        self.pTree.get_widget('prefsDlg').hide()
#
#    def prefs_commit(self, widget):
#        """Callback for OKing changes to the preferences"""
#        # Update the time settings for each mode.
#        for mode in self.model.timers:
#            widget_spin = 'spinBtn_%sMode' % mode.name.lower()
#            widget = self.pTree.get_widget(widget_spin)
#            mode.total = (widget.get_value() * 3600)
#
#        notify_box = self.pTree.get_widget('checkbutton_notify')
#        self.model.notify = notify_box.get_active()
#
#        # Remaining cleanup.
#        self.update_progressBars()
#        self.pTree.get_widget('prefsDlg').hide()
