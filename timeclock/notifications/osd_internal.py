"""A simple notifier which displays a non-dismissable OSD with increasing
timeouts when a timer overruns.
"""
from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import gobject
from ..ui.util import MultiMonitorOSD

class OSDNaggerNotifier(gobject.GObject):
    """A timer expiry notification view based on an unmanaged window."""
    def __init__(self, model):
        super(OSDNaggerNotifier, self).__init__()

        self.osd = MultiMonitorOSD(model)

        model.connect('notify-tick', self.cb_notify_exhaustion)
        model.connect('mode-changed', self.cb_mode_changed)

    def cb_mode_changed(self, model, mode):  # pylint: disable=unused-argument
        """Hides any old OSDs when the timer mode is changed"""
        self.osd.hide()

    # pylint: disable=unused-argument
    def cb_notify_exhaustion(self, model, mode):
        """Display an OSD on each monitor"""
        #TODO: The message template should be separated.
        #TODO: I need to also display some kind of message expiry countdown
        #XXX: Should I use a non-linear mapping for timeout?
        #FIXME: This doesn't yet get along with overtime.
        self.osd.message("Timer Expired: %s" % mode.name,
                abs(min(-5, mode.remaining() / 60)))
