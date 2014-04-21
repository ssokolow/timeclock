"""A timer expiry notifier based on libnotify popups"""

# TODO: Rearchitect to deduplicate this __appname__ definition
__appname__ = "The Procrastinator's Timeclock"
__authors__ = [
    "Stephan Sokolow (deitarion/SSokolow)",
    "Charlie Nolan (FunnyMan3595)"]
__author__ = ', '.join(__authors__)
__license__ = "GNU GPL 2.0 or later"

import gobject, gtk
from ..ui.util import get_icon_path

class LibNotifyNotifier(gobject.GObject):
    """A timer expiry notification view based on libnotify.

    :todo: Redesign this on an abstraction over Growl, libnotify, and toasts.
    """
    pynotify = None
    error_dialog = None

    def __init__(self, model):
        # ImportError should be caught when instantiating this.
        import pynotify
        from xml.sax.saxutils import escape as xmlescape

        # Do this second because I'm unfamiliar with GObject refcounting.
        super(LibNotifyNotifier, self).__init__()

        # Only init PyNotify once
        if not self.pynotify:
            pynotify.init(__appname__)
            self.__class__.pynotify = pynotify

        # Make the notifications in advance,
        self.last_notified = 0
        self.notifications = {}
        for mode in model.timers:
            notification = pynotify.Notification(
                "%s Time Exhausted" % mode.name,
                "You have used all allotted time for %s" %
                    xmlescape(mode.name.lower()),
                get_icon_path(48))
            notification.set_urgency(pynotify.URGENCY_NORMAL)
            notification.set_timeout(pynotify.EXPIRES_NEVER)
            notification.last_shown = 0
            self.notifications[mode.name] = notification

            mode.connect('notify-tick', self.notify_exhaustion)

    def notify_exhaustion(self, mode):
        """Display a libnotify notification that the given timer has expired"""
        try:
            self.notifications[mode.name].show()
        except gobject.GError:
            if not self.error_dialog:
                self.error_dialog = gtk.MessageDialog(
                        type=gtk.MESSAGE_ERROR,
                        buttons=gtk.BUTTONS_CLOSE)
                self.error_dialog.set_markup("Failed to display a notification"
                        "\nMaybe your notification daemon crashed.")
                self.error_dialog.connect("response",
                        lambda widget, data=None: widget.hide())
            self.error_dialog.show()
