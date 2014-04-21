"""Controller to automatically reset the timer after a night's worth of
inactivity.
"""

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

import time
import gobject

# TODO: Make this configurable
SLEEP_RESET_INTERVAL = 3600 * 6  # 6 hours

class IdleController(gobject.GObject):
    """A controller to automatically reset the timer if you fall asleep."""
    watch_id, conn = None, None

    def __init__(self, model):
        super(IdleController, self).__init__()
        self._source_remove = gobject.source_remove
        #See SingleInstance for rationale

        self.model = model
        self.last_tick = 0

        try:
            import xcb, xcb.xproto
            import xcb.screensaver
        except ImportError:
            pass
        else:
            self.conn = xcb.connect()
            self.setup = self.conn.get_setup()
            self.ss_conn = self.conn(xcb.screensaver.key)

            #TODO: Also handle gobject.IO_HUP in case of disconnect.
            self.watch_id = gobject.io_add_watch(
                    self.conn.get_file_descriptor(),
                    gobject.IO_IN | gobject.IO_PRI,
                    self.cb_xcb_response)

            model.connect('updated', self.cb_updated)

    def __del__(self):
        if self.watch_id:
            self._source_remove(self.watch_id)
        if self.conn:
            self.conn.disconnect()

    def cb_updated(self, model):
        """Callback to check idle duration once per minute."""
        now = time.time()
        if self.last_tick + 60 < now:
            self.last_tick = now

            #TODO: Can I do this with cb_xcb_response for less blocking?
            idle_query = self.ss_conn.QueryInfo(self.setup.roots[0].root)
            idle_secs = idle_query.reply().ms_since_user_input / 1000.0

            #FIXME: This will fire once a second once the limit is passed
            if idle_secs >= SLEEP_RESET_INTERVAL:
                model.reset()

    def cb_xcb_response(self, source, condition):
        """Accept and discard X events to prevent any risk of a frozen
        connection because some buffer somewhere is full.

        :todo: Decide how to handle conn.has_error() != 0 (disconnected)
        :note: It's safe to call conn.disconnect() multiple times.
        """
        try:
            # (Don't use "while True" in case the xcb "NULL when no more"
            #  behaviour occasionally happens)
            while self.conn.poll_for_event():
                pass
        except IOError:
            # In testing, IOError is raised when no events are available.
            pass

        return True  # Keep the callback registered.
