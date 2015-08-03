"""Controller to nag you into going AFK for a defined part of the day."""
from __future__ import absolute_import

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import logging, random, string  # pylint: disable=deprecated-module
from datetime import datetime, time, timedelta

from dateutil.rrule import rrule, DAILY
from setproctitle import setproctitle, getproctitle  # pylint: disable=E0611

import gobject, pango

from ..ui.util import MultiMonitorOSD

MIN_NOTIFICATION_SIZE = (750, 550)

# NOTE: Times are in UTC (EST = UTC-5, EDT = UTC-4)
DEFAULTS = {
    # TODO: Make these persistent, configurable settings
    'bedtime': time(hour=8),
    'sleep_duration': timedelta(hours=7),  # Minimum allowed
    'snooze_duration': timedelta(minutes=20),
    'update_interval': timedelta(minutes=1)
}

log = logging.getLogger(__name__)

def get_random_proctitle():
    """Return a 16-character alphanumeric string

    Sources:
        - http://stackoverflow.com/a/2257449/435253
        - http://stackoverflow.com/a/23534499/435253
    """
    return ''.join(random.SystemRandom().choice(
        string.ascii_letters + string.digits) for _ in range(16))

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

    def __init__(self, model):  # pylint: disable=E1002
        super(BedtimeEnforcer, self).__init__()
        self.config = DEFAULTS.copy()
        self.config.update(getattr(model, 'bedtime_enforcer', {}))

        self.model = model
        self.orig_proctitle = getproctitle()
        self.last_tick = self.epoch
        self.bedtime = rrule(DAILY,
                             byhour=self.config['bedtime'].hour,
                             byminute=self.config['bedtime'].minute,
                             bysecond=self.config['bedtime'].second,
                             dtstart=self.epoch)
        self.alert_start = self.epoch
        self.alert_end = self.epoch

        now = datetime.utcnow()
        self._upd_alert_time(now)
        self._update_alerting(now)

        self.osd = MultiMonitorOSD(cycle=True, pad_to=MIN_NOTIFICATION_SIZE,
                                   # pylint: disable=E1101
                                   font=pango.FontDescription("Sans Serif 64"))
        model.connect('updated', self.cb_updated)

        self.has_snoozed = False
        model.add_action("Snooze", self.cb_snooze)
        # TODO: Make Snooze only active while alerting

    def cb_snooze(self, _):
        now = datetime.utcnow()
        self.alert_start = now + self.config['snooze_duration']
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
                setproctitle(get_random_proctitle())
                self.model.emit("action-set-enabled",
                                "Snooze", not self.has_snoozed)
        else:
            log.debug("Not %s < %s < %s",
                      self.alert_start, now, self.alert_end)
            self.osd.hide()
            if not self.has_snoozed:
                self.model.suppress_shutdown = False
                if old_suppress != self.model.suppress_shutdown:
                    setproctitle(self.orig_proctitle)
                    self.model.emit("action-set-enabled", "Snooze", False)

    def _upd_alert_time(self, now):
        self.alert_end = self.alert_start + self.config['sleep_duration']
        if self.alert_start < now and self.alert_end < now:
            self.has_snoozed = False
            self.alert_start = self.bedtime.before(now)
            self.alert_end = self.alert_start + self.config['sleep_duration']

    def cb_updated(self, model):
        """Callback to check the time duration once per minute."""
        now = datetime.utcnow()

        # TODO: Deduplicate this logic without tripping over the GObject
        #       event loop bug.
        if self.last_tick + self.config['update_interval'] < now:
            self.last_tick = now
            self._upd_alert_time(now)
            self._update_alerting(now)
