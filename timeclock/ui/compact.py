"""Compact, toolbar-like UI"""

from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import logging

import gtk

from .common import ModeWidgetMixin, MainWinMixin
from .util import get_icon_path, RoundedWindow

log = logging.getLogger(__name__)

# pylint: disable=too-many-ancestors,too-many-public-methods
class ModeButton(gtk.RadioButton, ModeWidgetMixin):  # pylint: disable=E1101
    """Compact progress-button representing a timer mode."""

    progress_label = lambda _, mode: str(mode)

    def __init__(self, mode, *args, **kwargs):
        super(ModeButton, self).__init__(*args, **kwargs)

        self.mode = mode
        self.button = self  # XXX: Is there any potential harm in this?
        self.progress = gtk.ProgressBar()  # pylint: disable=E1101

        self._init_children()

        self.add(self.progress)  # pylint: disable=E1101

class MainWin(RoundedWindow, MainWinMixin):
    """Compact UI suitable for overlaying on titlebars"""
    def __init__(self, model):
        # Silence PyLint's spurious "module 'gtk' has no member ..." warnings
        # pylint: disable=E1101

        super(MainWin, self).__init__()
        self.set_resizable(False)

        self.model = model
        self.evbox = gtk.EventBox()
        self.box = gtk.HBox()
        self.btnbox = gtk.HButtonBox()
        self.menu = MainWinContextMenu(self)

        first_btn = None
        for mode in model.timers:
            btn = ModeButton(mode)
            btn.connect('toggled', self.cb_btn_toggled, btn)
            btn.connect('button-press-event', self.cb_show_menu)
            if mode.show:
                self.btnbox.add(btn)
            else:
                pass  # TODO: Hook up signals to share state with RadioMenuItem
                # RadioMenuItem can't share a group with RadioButton
                # ...so we fake it using hidden group members and signals.

            if first_btn:
                btn.set_group(first_btn)
            else:
                first_btn = btn

            model.connect('mode-changed', btn.cb_mode_changed)

        drag_handle = gtk.Image()
        handle_evbox = gtk.EventBox()

        handle_evbox.add(drag_handle)
        self.box.add(handle_evbox)

        self.box.add(self.btnbox)

        self.evbox.add(self.box)
        self.add(self.evbox)
        self.set_decorated(False)
        # TODO: See if I can achieve something suitable using a window type too

        self.evbox.connect('button-release-event', self.cb_show_menu)
        # TODO: Make this work so the Menu key works.
        # self.evbox.connect('popup-menu', self.cb_show_menu)
        handle_evbox.connect('button-press-event', self.cb_handle_pressed)

        self._init_after()
        self.menu.show_all()  # TODO: Is this line necessary?
        self.show_all()

        # Drag handle cursor must be set after show_all()
        # pylint: disable=no-member
        handle_evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))

        # Set the icon after we know how much vert space the GTK theme gives us
        drag_handle.set_from_file(get_icon_path(
            drag_handle.get_allocation()[3]))

    # pylint: disable=unused-argument
    def cb_handle_pressed(self, widget, event):
        """Callback to power the drag handle by handing off to the WM.
        Sources:
         - http://www.gtkforums.com/viewtopic.php?t=1822
         - http://www.pygtk.org/docs/pygtk/class-gtkwindow.html
        """
        # we only want dragging via LMB (eg. preserve context menu)
        if event.button != 1:
            return False

        # Silence PyLint's spurious "module 'gtk' has no member ..." warnings
        # pylint: disable=E1101
        self.begin_move_drag(event.button,
                             int(event.x_root), int(event.y_root),
                             event.time)

    def cb_show_menu(self, widget, event=None, data=None):
        """Callback to trigger the context menu on right-click only"""
        if event:
            evtBtn, evtTime = event.button, event.get_time()

            if evtBtn != 3:
                return False
        else:
            evtBtn, evtTime = None, None

        # Silence PyLint's spurious "module 'gtk' has no member ..." warnings
        # pylint: disable=E1101
        self.menu.popup(None, None, None, 3, evtTime)

        return True

class MainWinContextMenu(gtk.Menu):  # pylint: disable=E1101,R0903
    """Context menu for `MainWinCompact`"""
    def __init__(self, mainwin, *args, **kwargs):  # pylint: disable=E1002
        super(MainWinContextMenu, self).__init__(*args, **kwargs)
        self.model = mainwin.model
        self.actions = {}

        # Silence PyLint's spurious "module 'gtk' has no member ..." warnings
        # pylint: disable=E1101
        asleep = gtk.RadioMenuItem(None, "_Asleep")
        reset = gtk.MenuItem("_Reset...")
        sep = gtk.SeparatorMenuItem()
        prefs = gtk.MenuItem("_Preferences...")
        self.quit_item = gtk.ImageMenuItem(stock_id="gtk-quit")

        self.append(asleep)
        self.append(reset)
        self.append(sep)
        self.append(prefs)
        self.append(self.quit_item)

        self.model.connect('updated',
                           self.cb_model_updated)
        self.model.connect('action-added', self.cb_action_added)
        self.model.connect('action-set-enabled', self.cb_action_set_enabled)
        for label, callback in self.model.actions:
            self.cb_action_added(label, callback)

        # TODO: asleep
        reset.connect('activate', mainwin.cb_reset, mainwin.model)
        # TODO: prefs
        self.quit_item.connect('activate', gtk.main_quit)

    def cb_model_updated(self, model):
        self.quit_item.set_sensitive(not model.suppress_shutdown)
        # TODO: Do more than this

    def cb_action_set_enabled(self, _, action, is_enabled):
        log.debug("Action toggled: %s -> %s", action, is_enabled)
        widget = self.actions.get(action)
        if widget:
            widget.set_sensitive(is_enabled)
        else:
            log.warning("Unrecognized action (Compact UI): %s", action)

    def cb_action_added(self, label, callback):
        # pylint: disable=E1101
        menuitem = gtk.MenuItem(label)
        menuitem.connect('activate', callback)

        # FIXME: Insert, not append. (How do I get the desired position?)
        self.append(menuitem)
        self.actions[label] = menuitem
