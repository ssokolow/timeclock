from __future__ import absolute_import

import gobject, gtk
from ..ui.util import OSDWindow

class OSDNaggerNotifier(gobject.GObject):
    """A timer expiry notification view based on an unmanaged window."""
    def __init__(self, model):
        super(OSDNaggerNotifier, self).__init__()

        self.windows = {}

        display_manager = gtk.gdk.display_manager_get()
        for display in display_manager.list_displays():
            self.cb_display_opened(display_manager, display)

        model.connect('notify-tick', self.cb_notify_exhaustion)
        model.connect('mode-changed', self.cb_mode_changed)
        display_manager.connect("display-opened", self.cb_display_opened)

    def cb_display_closed(self, display, is_error):
        pass  # TODO: Dereference and destroy the corresponding OSDWindows.

    def cb_display_opened(self, manager, display):
        for screen_num in range(0, display.get_n_screens()):
            screen = display.get_screen(screen_num)

            self.cb_monitors_changed(screen)
            screen.connect("monitors-changed", self.cb_monitors_changed)

        display.connect('closed', self.cb_display_closed)

    def cb_mode_changed(self, model, mode):
        for win in self.windows.values():
            win.hide()

    def cb_monitors_changed(self, screen):
        #FIXME: This must handle changes and deletes in addition to adds.
        for monitor_num in range(0, screen.get_n_monitors()):
            display_name = screen.get_display().get_name()
            screen_num = screen.get_number()
            geom = screen.get_monitor_geometry(monitor_num)

            key = (display_name, screen_num, tuple(geom))
            if key not in self.windows:
                window = OSDWindow()
                window.set_screen(screen)
                window.set_gravity(gtk.gdk.GRAVITY_CENTER)
                window.move(geom.x + geom.width / 2, geom.y + geom.height / 2)
                #FIXME: Either fix the center gravity or calculate it manually
                # (Might it be that the window hasn't been sized yet?)
                self.windows[key] = window

    # pylint: disable=unused-argument
    def cb_notify_exhaustion(self, model, mode):
        """Display an OSD on each monitor"""
        for win in self.windows.values():
            #TODO: The message template should be separated.
            #TODO: I need to also display some kind of message expiry countdown
            #XXX: Should I use a non-linear mapping for timeout?
            #FIXME: This doesn't yet get along with overtime.
            win.message("Timer Expired: %s" % mode.name,
                    abs(min(-5, mode.remaining() / 60)))
