import gtk

from util import get_icon_path, RoundedWindow

class ModeButton(gtk.RadioButton):
    """Compact progress-button representing a timer mode."""
    def __init__(self, mode, *args, **kwargs):
        super(ModeButton, self).__init__(*args, **kwargs)

        self.mode = mode

        self.progress = gtk.ProgressBar()
        self.add(self.progress)

        self.set_mode(False)
        self.progress.set_fraction(1.0)
        self.update_label(mode)

        mode.connect('updated', self.update_label)

    def mode_changed(self, model, mode):
        """Bind this to the 'mode-changed' signal on the top-level model.

        (Must be bound by MainWin if things are to remain modular)
        """
        if mode == self.mode and not self.get_active():
            self.set_active(True)

    def update_label(self, mode):
        self.progress.set_text(str(mode))
        self.progress.set_fraction(
                max(float(mode.remaining()) / mode.total, 0))

class MainWinContextMenu(gtk.Menu):
    """Context menu for `MainWinCompact`"""
    def __init__(self, model, *args, **kwargs):
        super(MainWinContextMenu, self).__init__(*args, **kwargs)
        self.model = model

        asleep = gtk.RadioMenuItem(None, "_Asleep")
        reset = gtk.MenuItem("_Reset...")
        sep = gtk.SeparatorMenuItem()
        prefs = gtk.MenuItem("_Preferences...")
        quit = gtk.ImageMenuItem(stock_id="gtk-quit")

        self.append(asleep)
        self.append(reset)
        self.append(sep)
        self.append(prefs)
        self.append(quit)

        #TODO: asleep
        reset.connect('activate', self.cb_reset)
        #TODO: prefs
        quit.connect('activate', gtk.main_quit)

    def cb_reset(self, widget):
       #TODO: Look into how to get MainWinCompact via parent-lookup calls so
        # this can be destroyed with its parent.
        confirm = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Reset all timers?\n"
                "Warning: This operation cannot be undone.")
        if confirm.run() == gtk.RESPONSE_OK:
            self.model.reset()
        confirm.destroy()

class MainWinCompact(RoundedWindow):
    """Compact UI suitable for overlaying on titlebars"""
    def __init__(self, model):
        super(MainWinCompact, self).__init__()
        self.set_icon_from_file(get_icon_path(64))
        self.set_resizable(False)

        self.model = model
        self.evbox = gtk.EventBox()
        self.box = gtk.HBox()
        self.btnbox = gtk.HButtonBox()
        self.menu = MainWinContextMenu(model)

        first_btn = None
        for mode in model.timers:
            btn = ModeButton(mode)
            btn.connect('toggled', self.btn_toggled)
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

            model.connect('mode-changed', btn.mode_changed)

        drag_handle = gtk.Image()
        handle_evbox = gtk.EventBox()

        handle_evbox.add(drag_handle)
        self.box.add(handle_evbox)

        self.box.add(self.btnbox)

        self.evbox.add(self.box)
        self.add(self.evbox)
        self.set_decorated(False)
        #TODO: See if I can achieve something suitable using a window type too.

        # Because window-state-event is broken on many WMs, default to sticky,
        # on top as a most likely default for users. (TODO: Preferences toggle)
        self.set_keep_above(True)
        self.stick()

        self.model.connect('updated', self.update)
        self.model.connect('mode-changed', self.mode_changed)
        self.evbox.connect('button-release-event', self.showMenu)
        # TODO: Make this work so the Menu key works.
        #self.evbox.connect('popup-menu', self.showMenu)
        handle_evbox.connect('button-press-event', self.handle_pressed)

        self.update(model)
        self.menu.show_all()  # TODO: Is this line necessary?
        self.show_all()

        # Drag handle cursor must be set after show_all()
        handle_evbox.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))

        # Set the icon after we know how much vert space the GTK theme gives us
        drag_handle.set_from_file(get_icon_path(
            drag_handle.get_allocation()[3]))

    #TODO: Normalize callback naming
    def btn_toggled(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active() and not self.model.selected == widget.mode:
            self.model.selected = widget.mode

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

    def mode_changed(self, model, mode):
        self.update(model)

    def update(self, model):
        self.set_title(str(model.selected))

    def showMenu(self, widget, event=None, data=None):
        if event:
            evtBtn, evtTime = event.button, event.get_time()

            if evtBtn != 3:
                return False
        else:
            evtBtn, evtTime = None, None

        self.menu.popup(None, None, None, 3, evtTime)

        return True
