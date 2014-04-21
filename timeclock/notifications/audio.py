"""GStreamer-based audio notifier for timer expiry"""

import os, sys
import gobject

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

# TODO: Make this configurable
NOTIFY_SOUND = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'sound.wav')

class AudioNotifier(gobject.GObject):
    """An audio timer expiry notification based on a portability layer."""
    def __init__(self, model):
        # Keep "import gst" from grabbing --help, showing its help, and exiting
        _argv, sys.argv = sys.argv, []

        try:
            import gst
            import urllib
        finally:
            # Restore sys.argv so I can parse it cleanly.
            sys.argv = _argv

        self.gst = gst
        super(AudioNotifier, self).__init__()

        self.last_notified = 0
        self.uri = NOTIFY_SOUND

        if os.path.exists(self.uri):
            self.uri = 'file://' + urllib.pathname2url(
                    os.path.abspath(self.uri))
        self.bin = gst.element_factory_make("playbin")
        self.bin.set_property("uri", self.uri)

        model.connect('notify-tick', self.cb_notify_exhaustion)

        #TODO: Fall back to using winsound or wave+ossaudiodev or maybe pygame
        #TODO: Design a generic wrapper which also tries things like these:
        # - http://stackoverflow.com/q/276266/435253
        # - http://stackoverflow.com/questions/307305/play-a-sound-with-python

    # pylint: disable=unused-argument
    def cb_notify_exhaustion(self, model, mode):
        """Callback which actually fires off the notification"""
        #TODO: Do I really need to set STATE_NULL first?
        self.bin.set_state(self.gst.STATE_NULL)
        self.bin.set_state(self.gst.STATE_PLAYING)
