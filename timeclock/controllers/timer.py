"""The code which actually makes the timer tick."""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import time
import gobject

# TODO: Make this configurable
SAVE_INTERVAL = 60 * 5  # 5 Minutes
NOTIFY_INTERVAL = 60 * 15  # 15 Minutes

class TimerController(gobject.GObject):
    """The default timer behaviour for the timeclock."""
    def __init__(self, model):
        super(TimerController, self).__init__()

        self.model = model
        self.last_tick = time.time()
        self.last_notify = 0

        model.connect('mode-changed', self.cb_mode_changed)
        gobject.timeout_add(1000, self.tick)

    def tick(self):
        """Callback for updating progress bars."""
        now = time.time()
        selected = self.model.selected
        active = self.model.active

        delta = now - self.last_tick
        notify_delta = now - self.last_notify

        selected.used += delta
        if selected != active:
            active.used += delta

        #TODO: Decide what to do if both selected and active are expired.
        if selected.remaining() <= 0 and notify_delta > NOTIFY_INTERVAL:
            selected.cb_notify_tick()
            self.last_notify = now

        if active.remaining() < 0:
            overflow_to = ([x for x in self.model.timers
                if x.name == active.overflow] or [None])[0]
            if overflow_to:
                self.model.active = overflow_to
                #XXX: Is it worth fixing the pseudo-rounding error tick, delta,
                # and mode-switching introduce?

        if now >= (self.model.last_save + SAVE_INTERVAL):
            self.model.save()

        self.last_tick = now
        return True

    def cb_mode_changed(self, model, mode):
        """Callback which ensures that an expiry notification will appear
           immediately if you change to an empty timer."""
        self.last_notify = 0
