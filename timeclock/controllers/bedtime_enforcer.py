"""Controller to nag you into going AFK for a defined part of the day."""
from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import logging
from datetime import datetime, time, timedelta

from dateutil.rrule import rrule, DAILY

import gobject, pango

from ..ui.util import MultiMonitorOSD


if True:
    # Test code
    now = datetime.utcnow()
    BEDTIME = time(hour=now.hour, minute=now.minute, second=now.second)
    SLEEP_DURATION = timedelta(seconds=10)  # Minimum allowed
    SNOOZE_DURATION = timedelta(seconds=5)
    UPD_INTERVAL = timedelta(seconds=1)
else:
    # TODO: Make these configurable
    # NOTE: Times are in UTC (EST = UTC-5, EDT = UTC-4)
    BEDTIME = time(hour=7)
    SLEEP_DURATION = timedelta(hours=8)  # Minimum allowed
    SNOOZE_DURATION = timedelta(minutes=20)
    UPD_INTERVAL = timedelta(minutes=1)

log = logging.getLogger(__name__)

class BedtimeEnforcer(gobject.GObject):  # pylint: disable=R0903,E1101
    """Very early draft to enforce a sleep cycle.

    @todo: Use a multi-process model so that quitting Timeclock doesn't
           dismiss the nag and it is just respawned if it's killed while
           active.
    @todo: Once I've moved the input idleness detection into core and added
           a joystick backend, add an option to automatically adjust the
           time when it starts nagging in order to learn the correct
           tunings to produce the desired sleep cycle.
    """
    epoch = datetime.utcfromtimestamp(0)
    upd_interval = UPD_INTERVAL

    def __init__(self, model):  # pylint: disable=E1002
        super(BedtimeEnforcer, self).__init__()
        self.model = model
        self.last_tick = self.epoch
        self.bedtime = rrule(DAILY,
                             byhour=BEDTIME.hour,
                             byminute=BEDTIME.minute,
                             bysecond=BEDTIME.second,
                             dtstart=self.epoch)
        self.alert_start = self.epoch
        self.alert_end = self.epoch
        self._upd_alert_time(datetime.utcnow(), force=True)

        self.osd = MultiMonitorOSD(cycle=True,
                                   # pylint: disable=E1101
                                   font=pango.FontDescription("Sans Serif 64"))
        model.connect('updated', self.cb_updated)

        self.has_snoozed = False
        model.add_action("Snooze", self.cb_snooze)
        # TODO: Make Snooze only active while alerting

    def cb_snooze(self, _):
        now = datetime.utcnow()
        self.alert_start = now + SNOOZE_DURATION
        self._upd_alert_time(now)
        self.model.emit("action-set-enabled", "Snooze", False)
        self.has_snoozed = True

        self._update_alerting(now)

    def _update_alerting(self, now):
        old_suppress = self.model.suppress_shutdown
        if self.alert_start < now < self.alert_end:
            log.debug("%s < %s < %s", self.alert_start, now, self.alert_end)
            self.model.suppress_shutdown = True
            self.osd.message("Go The @#$% To Sleep!", -1)

            # TODO: Centralize this edge-event generation
            if old_suppress != self.model.suppress_shutdown:
                self.model.emit("action-set-enabled",
                                "Snooze", not self.has_snoozed)
        else:
            log.debug("Not %s < %s < %s",
                      self.alert_start, now, self.alert_end)
            self.osd.hide()
            if not self.has_snoozed:
                self.model.suppress_shutdown = False
                if old_suppress != self.model.suppress_shutdown:
                    self.model.emit("action-set-enabled", "Snooze", False)

    def _upd_alert_time(self, now, force=False):
        self.alert_end = self.alert_start + SLEEP_DURATION
        if self.alert_start < now and self.alert_end < now:
            self.has_snoozed = False
            self.alert_start = self.bedtime.before(now)
            self.alert_end = self.alert_start + SLEEP_DURATION

    def cb_updated(self, model):
        """Callback to check the time duration once per minute."""
        now = datetime.utcnow()

        # TODO: Deduplicate this logic without tripping over the GObject
        #       event loop bug.
        if self.last_tick + self.upd_interval < now:
            self.last_tick = now
            self._upd_alert_time(now)
            self._update_alerting(now)
