"""Controller to nag you into going AFK for a defined part of the day."""
from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import time
from datetime import datetime

import gobject, pango

from ..ui.util import MultiMonitorOSD

BEDTIME = 0

class BedtimeEnforcer(gobject.GObject):
    """Very early draft to enforce a sleep cycle.

    @todo: Use a multi-process model so that quitting Timeclock doesn't
           dismiss the nag and it is just respawned if it's killed while
           active.
    @todo: Once I've moved the input idleness detection into core and added
           a joystick backend, add an option to automatically adjust the
           time when it starts nagging in order to learn the correct
           tunings to produce the desired sleep cycle.
    """
    def __init__(self, model):
        super(BedtimeEnforcer, self).__init__()
        self.model = model
        self.last_tick = 0
        self.osd = MultiMonitorOSD(cycle=True,
            font=pango.FontDescription("Sans Serif 64"))
        model.connect('updated', self.cb_updated)

    def cb_updated(self, model):
        """Callback to check the time duration once per minute."""
        now = time.time()

        # TODO: Deduplicate this logic without tripping over the GObject
        #       event loop bug.
        if self.last_tick + 60 < now:
            self.last_tick = now

            # TODO: Make this configurable
            hour = datetime.fromtimestamp(now).hour
            waketime = (BEDTIME + 6) % 24

            # TODO: Is there a more elegant way to do this?
            alerting = False
            if waketime > BEDTIME and BEDTIME <= hour < waketime:
                alerting = True
            elif waketime < BEDTIME and (BEDTIME <= hour or hour < waketime):
                alerting = True

            if alerting:
                self.osd.message("Go The @#$% To Sleep!", -1)
            else:
                self.osd.hide()
