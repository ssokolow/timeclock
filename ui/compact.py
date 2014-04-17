from __future__ import absolute_import

import gtk

from .common import ModeWidgetMixin, MainWinMixin
from .util import get_icon_path, RoundedWindow

class ModeButton(gtk.RadioButton, ModeWidgetMixin):
    """Compact progress-button representing a timer mode."""

    progress_label = lambda _, mode: str(mode)

    def __init__(self, mode, *args, **kwargs):
        super(ModeButton, self).__init__(*args, **kwargs)

        self.mode = mode
        self.button = self  # XXX: Is there any potential harm in this?
        self.progress = gtk.ProgressBar()

        self._init_children()

        self.add(self.progress)

class MainWin(RoundedWindow, MainWinMixin):
    """Compact UI suitable for overlaying on titlebars"""
    def __init__(self, model):
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
            btn.connect('button-press-event', self.showMenu)
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
        #TODO: See if I can achieve something suitable using a window type too.

        self.evbox.connect('button-release-event', self.showMenu)
        # TODO: Make this work so the Menu key works.
        #self.evbox.connect('popup-menu', self.showMenu)
        handle_evbox.connect('button-press-event', self.handle_pressed)

        self._init_after()
        self.menu.show_all()  # TODO: Is this line necessary?
        self.show_all()

        # Drag handle cursor must be set after show_all()
        handle_evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))

        # Set the icon after we know how much vert space the GTK theme gives us
        drag_handle.set_from_file(get_icon_path(
            drag_handle.get_allocation()[3]))

    def handle_pressed(self, widget, event):
        """If possible, let the WM do window dragging
        Sources:
         - http://www.gtkforums.com/viewtopic.php?t=1822
         - http://www.pygtk.org/docs/pygtk/class-gtkwindow.html
        """
        # we only want dragging via LMB (eg. preserve context menu)
        if event.button != 1:
            return False
        self.begin_move_drag(event.button,
                int(event.x_root), int(event.y_root),
                event.time)

    def showMenu(self, widget, event=None, data=None):
        if event:
            evtBtn, evtTime = event.button, event.get_time()

            if evtBtn != 3:
                return False
        else:
            evtBtn, evtTime = None, None

        self.menu.popup(None, None, None, 3, evtTime)

        return True

class MainWinContextMenu(gtk.Menu):
    """Context menu for `MainWinCompact`"""
    def __init__(self, mainwin, *args, **kwargs):
        super(MainWinContextMenu, self).__init__(*args, **kwargs)
        self.model = mainwin.model

        asleep = gtk.RadioMenuItem(None, "_Asleep")
        reset = gtk.MenuItem("_Reset...")
        sep = gtk.SeparatorMenuItem()
        prefs = gtk.MenuItem("_Preferences...")
        quit_item = gtk.ImageMenuItem(stock_id="gtk-quit")

        self.append(asleep)
        self.append(reset)
        self.append(sep)
        self.append(prefs)
        self.append(quit_item)

        #TODO: asleep
        reset.connect('activate', mainwin.cb_reset, mainwin.model)
        #TODO: prefs
        quit_item.connect('activate', gtk.main_quit)
