#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.
See http://ssokolow.github.com/timeclock/ for a screenshot.

@todo: Update site to reflect PyGTK 2.8 being required for PyCairo.

@todo: Optionally use idle detection to auto-trigger Overhead on wake
 - http://msdn.microsoft.com/en-us/library/ms646302.aspx (pywin32?)
 - http://stackoverflow.com/questions/608710/monitoring-user-idle-time
 - Probably a good idea to write and share a wrapper

@todo: Planned improvements:
 - Amend SingleInstance to show() and/or raise() a provided main window if none
   is found.
 - Look into offering an IdleController mode for people who turn their PCs off.
   - In fact, look into offering generic support for taking into account time
     with the timeclock turned off.
 - Strip out all these super() calls since it's still easy to introduce subtle
   bugs by forgetting to super() to the top of every branch of the hierarchy.
 - Decide whether overflow_to should cascade.
 - Double-check that it still works on Python 2.4.
 - Have the system complain if overhead + work + leisure + sleep (8 hours) > 24
   and enforce minimums of 1 hour for leisure and overhead.
 - Clicking the preferences button while the dialog is shown shouldn't reset
   the unsaved preference changes.
 - Extend the single-instance system to use D-Bus if available to raise/focus
   the existing instance if one is already running.
 - Figure out some intuitive, non-distracting way to allow the user to make
   corrections. (eg. you forgot to set the timer to leisure before going AFK)
 - Report PyGTK's uncatchable xkill response on the bug tracker.
 - Explore how progress bars behave when their base colors are changed:
   (http://hg.atheme.org/audacious/audacious-plugins/diff/a25b618e8f4a/src/gtkui/ui_playlist_widget.c)
 - Profile timeclock. Something this size shouldn't take 0.6% of an Athon 5000+

@todo: Notification TODO:
 - Offer to turn the timer text a user-specified color (default: red) when it
   goes into negative values.
 - Set up a callback for timer exhaustion.
 - Handle popup notifications more intelligently (eg. Explicitly hide them when
   switching away from an expired timer and explicitly show them when switching
   to one)

@todo: Consider:
 - Look into integrating with http://projecthamster.wordpress.com/

@todo: Publish this on listing sites:
 - http://gtk-apps.org/
 - http://pypi.python.org/pypi

@todo: Make use of these references:
 - http://www.pygtk.org/articles/writing-a-custom-widget-using-pygtk/writing-a-custom-widget-using-pygtk.htm
 - http://unpythonic.blogspot.com/2007/03/custom-pygtk-widgets-in-glade3-part-2.html
 - https://live.gnome.org/Vala/CustomWidgetSamples

@newfield appname: Application Name
"""

__appname__ = "The Procrastinator's Timeclock"
__authors__  = [
    "Stephan Sokolow (deitarion/SSokolow)",
    "Charlie Nolan (FunnyMan3595)"]
__author__ = ', '.join(__authors__)
__version__ = "0.2.99.0"
__license__ = "GNU GPL 2.0 or later"

default_timers = [
    {
        'class': 'UnlimitedMode',
        'name': 'Asleep',
        'total': int(3600 * 8),
        'used': 0,
    },
    {
        'name': 'Overhead',
        'total': int(3600 * 3.5),
        'used': 0,
        'overflow': 'Leisure'
    },
    {
        'name': 'Work',
        'total': int(3600 * 6.0),
        'used': 0,
    },
    {
        'name': 'Leisure',
        'total': int(3600 * 5.5),
        'used': 0,
    }
]

import copy, logging, os, signal, sys, tempfile, time, pickle

from ui.util import get_icon_path, RoundedWindow
from ui.compact import MainWinCompact
from ui.legacy import TimeClock

SELF_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.environ.get('XDG_DATA_HOME',
        os.path.expanduser('~/.local/share'))
SAVE_FILE = os.path.join(DATA_DIR, "timeclock.sav")

if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        raise SystemExit("Aborting: %s exists but is not a directory!"
                         % DATA_DIR)

SAVE_INTERVAL = 60 * 5  # 5 Minutes
SLEEP_RESET_INTERVAL = 3600 * 6  # 6 hours
NOTIFY_INTERVAL = 60 * 15  # 15 Minutes

NOTIFY_SOUND = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '49213__tombola__Fisher_Price29.wav')

DEFAULT_UI_LIST = ['compact', 'legacy']
DEFAULT_NOTIFY_LIST = ['audio', 'libnotify', 'osd']
file_exists = os.path.isfile

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

try:
    import pygtk
    pygtk.require("2.0")
except ImportError:
    pass

import cairo, gtk, gobject, pango
import gtk.gdk
import gtk.glade

import gtkexcepthook

class SingleInstance:
    """Source: http://stackoverflow.com/a/1265445/435253"""
    def __init__(self, useronly=True, lockfile=None, lockname=None):
        """
        :param useronly: Allow one instance per user rather than one instance
            overall. (On Windows, this is always True)
        :param lockfile: Specify an explicit path for the lockfile.
        :param lockname: Specify a filename to be used for the lockfile when
            ``lockfile`` is ``None``. The usual location selection algorithms
            and ``.lock`` extension will apply.

        :note: ``lockname`` assumes it is being given a valid filename.
        """
        import sys as _sys    # Alias to please pyflakes
        self.platform = _sys.platform  # Avoid an AttributeError in __del__

        if lockfile:
            self.lockfile = lockfile
        else:
            if lockname:
                fname = lockname + '.lock'
            else:
                fname = os.path.basename(__file__) + '.lock'
            if self.platform == 'win32' or not useronly:
                # According to TechNet, TEMP/TMP are already user-scoped.
                self.lockfile = os.path.join(tempfile.gettempdir(), fname)
            else:
                base = os.environ.get('XDG_CACHE_HOME',
                        os.path.expanduser('~/.cache'))
                self.lockfile = os.path.join(base, fname)

                if not os.path.exists(base):
                    os.makedirs(base)

        self.lockfile = os.path.normpath(os.path.normcase(self.lockfile))

        if self.platform == 'win32':  # TODO: What for Win64? os.name == 'nt'?
            try:
                # file already exists, we try to remove
                # (in case previous execution was interrupted)
                if(os.path.exists(self.lockfile)):
                    os.unlink(self.lockfile)
                self.fd = os.open(self.lockfile,
                        os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except OSError, e:
                if e.errno == 13:
                    print "Another instance is already running, quitting."
                    _sys.exit(-1)
                print e.errno
                raise
        else:  # non Windows
            import fcntl
            self.fp = open(self.lockfile, 'w')
            try:
                fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                print "Another instance is already running, quitting."
                _sys.exit(-1)

    def __del__(self):
        if self.platform == 'win32':
            if hasattr(self, 'fd'):
                os.close(self.fd)
                os.unlink(self.lockfile)

#{ Model stuff

def signalled_property(propname, signal_name):
    """Use property() to automatically emit a GObject signal on modification.

    :param propname: The name of the private member to back the property with.
    :param signal_name: The name of the GObject signal to emit.
    :type propname: str
    :type signal_name: str
    """
    def pget(self):
        """Default getter"""
        return getattr(self, propname)

    def pset(self, value):
        """Default setter plus signal emit"""
        setattr(self, propname, value)
        self.emit(signal_name)

    def pdel(self):
        """Default deleter"""
        delattr(self, propname)

    return property(pget, pset, pdel)

class Mode(gobject.GObject):
    """Data and operations for a timer mode"""
    __gsignals__ = {
        'notify-tick': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        'updated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    name = signalled_property('_name', 'updated')
    total = signalled_property('_total', 'updated')
    used = signalled_property('_used', 'updated')
    overflow = signalled_property('_overflow', 'updated')
    show = True

    def __init__(self, name, total, used=0, overflow=None):
        super(Mode, self).__init__()

        self._name = name
        self._total = total
        self._used = used
        self._overflow = overflow

    def __str__(self):
        remaining = round(self.remaining())
        if remaining >= 0:
            ptime = time.strftime('%H:%M:%S', time.gmtime(remaining))
        else:
            ptime = time.strftime('-%H:%M:%S', time.gmtime(abs(remaining)))

        return '%s: %s' % (self.name, ptime)

    def remaining(self):
        """Return the remaining time in this mode as an integer"""
        return self.total - self.used

    def reset(self):
        """Reset the timer and update listeners."""
        self.used = 0

    def save(self):
        """Serialize into a dict that can be used with __init__."""
        return {
                'class': self.__class__.__name__,
                'name': self.name,
                'total': self.total,
                'used': self.used,
                'overflow': self.overflow,
        }

    def notify_tick(self):
        self.emit('notify-tick')

class UnlimitedMode(Mode):
    """Data and operations for modes like Asleep"""
    show = False

    def __str__(self):
        return self.name

    def remaining(self):
        return 1  # TODO: Decide on a better way to do this.

SAFE_MODE_CLASSES = [Mode, UnlimitedMode]
CURRENT_SAVE_VERSION = 6  #: Used for save file versioning
class TimerModel(gobject.GObject):
    """Model class which still needs more refactoring."""
    __gsignals__ = {
        'mode-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (Mode,)),
        'notify_tick': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (Mode,)),
        'updated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    def __init__(self, start_mode=None, save_file=SAVE_FILE):
        super(TimerModel, self).__init__()

        self.last_save = 0
        self.save_file = save_file
        self.start_mode = start_mode

        self.notify = True
        self._load()
        # IMPORTANT: _load() MUST be called before signals are bound.

        #TODO: Still need to add "Asleep as an explicit mode" migration.
        self.start_mode = ([x for x in self.timers if x.name == start_mode] or
                [self.timers[0]])[0]
        self._selected = self.start_mode
        self.active = self.start_mode

        for mode in self.timers:
            mode.connect('updated', self.updated)
            mode.connect('notify-tick', self.notify_tick)

    def updated(self, mode):
        self.emit('updated')

    def notify_tick(self, mode):
        self.emit('notify-tick', mode)

    def reset(self):
        """Reset all timers to starting values"""
        for mode in self.timers:
            mode.reset()
        self.selected = self.start_mode

    def _load(self):
        """Load the save file if present. Log and start clean otherwise."""
        if file_exists(self.save_file):
            try:
                # Load the data, but leave the internal state unchanged in case
                # of corruption.

                # Don't rely on CPython's refcounting or Python 2.5's "with"
                fh = open(self.save_file, 'rb')
                loaded = pickle.load(fh)
                fh.close()

                #TODO: Move all the migration code to a different module.
                #TODO: Use old versions of Timeclock to generate unit test data

                version = loaded[0]
                if version == CURRENT_SAVE_VERSION:
                    version, data = loaded
                    timers = data.get('timers', [])
                    notify = data.get('window', {}).get('enable', True)
                    win_state = data.get('window', {})
                elif version == 5:
                    version, timers, notify, win_state = loaded

                    # Upgrade legacy configs with overflow
                    _ohead = [x for x in timers if x['name'] == 'Overhead']
                    if _ohead and not _ohead.get('overflow'):
                        _ohead['overflow'] = 'Leisure'
                elif version == 4:
                    version, total, used, notify, win_state = loaded
                elif version == 3:
                    version, total, used, notify = loaded
                    #win_state = {}
                elif version == 2:
                    version, total, used = loaded
                    notify = True
                    #win_state = {}
                elif version == 1:
                    version, total_old, used_old = loaded
                    translate = ["N/A", "btn_overheadMode", "btn_workMode",
                                 "btn_playMode"]
                    total = dict((translate.index(key), value)
                                 for key, value in total_old.items())
                    used = dict((translate.index(key), value)
                                for key, value in used_old.items())
                    notify = True
                    #win_state = {}
                else:
                    raise ValueError("Save file too new! (Expected %s, got %s)"
                            % (CURRENT_SAVE_VERSION, version))

                if version <= 4:
                    MODE_NAMES = ('Asleep', 'Overhead', 'Work', 'Leisure')

                    timers = []
                    for pos, row in enumerate(zip(total, used)):
                        timers.append({
                            'name': MODE_NAMES[pos],
                            'total': row[0],
                            'used': row[1],
                        })

                # Sanity checking could go here.

            except Exception, e:
                logging.error("Unable to load save file. Ignoring: %s", e)
                timers = copy.deepcopy(default_timers)
            else:
                logging.info("Save file loaded successfully")
                # File loaded successfully, now we put the data in place.
                self.notify = notify
                #self.app.saved_state = win_state
                #FIXME: Replace this with some kind of 'loaded' signal.

        else:
            timers = copy.deepcopy(default_timers)

        self.timers = []
        for data in timers:
            if 'class' in data:
                classname = data['class']
                del data['class']
            else:
                classname = 'Mode'

            cls = globals()[classname]
            if cls in SAFE_MODE_CLASSES:
                self.timers.append(cls(**data))
        #TODO: I need a way to trigger a rebuild of the view's signal bindings.

    #TODO: Reimplement using signalled_property and a signal connect.
    def _get_selected(self):
        return self._selected

    def _set_selected(self, mode):
        self._selected = mode
        self.active = mode
        #TODO: Figure out what class should bear responsibility for
        # automatically changing self.active when self.mode is changed.
        self.save()
        self.emit('mode-changed', mode)
    selected = property(_get_selected, _set_selected)

    def save(self):
        """Exit/Timeout handler for the app. Gets called every five minutes and
        on every type of clean exit except xkill. (PyGTK doesn't let you)

        Saves the current timer values to disk."""
        #TODO: Re-imeplement this properly.
        #window_state = {
        #         'position': self.app.win.get_position(),
        #        'decorated': self.app.win.get_decorated()
        #}
        window_state = {}
        timers = [mode.save() for mode in self.timers]

        data = {
            'timers': timers,
            'notify': {'enable': self.notify},
            'window': window_state,
        }

        # Don't rely on CPython's refcounting or Python 2.5's "with"
        fh = open(self.save_file + '.tmp', "wb")
        pickle.dump((CURRENT_SAVE_VERSION, data), fh)
        fh.close()

        # Windows doesn't let you os.rename to overwrite.
        # TODO: Find another way to atomically replace the state file.
        # TODO: Decide what to do when self.save_file is a directory
        if os.name == 'nt' and os.path.exists(self.save_file):
                os.unlink(self.save_file)

        # Corruption from saving without atomic replace has been observed
        os.rename(self.save_file + '.tmp', self.save_file)
        self.last_save = time.time()
        return True

#{ Controller Modules

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
        if selected.remaining() <= 0 and notify_delta > 900:
            selected.notify_tick()
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
        self.last_notify = 0

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

#{ Notification Modules

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

        model.connect('notify-tick', self.notify_exhaustion)

        #TODO: Fall back to using winsound or wave+ossaudiodev or maybe pygame
        #TODO: Design a generic wrapper which also tries things like these:
        # - http://stackoverflow.com/q/276266/435253
        # - http://stackoverflow.com/questions/307305/play-a-sound-with-python

    def notify_exhaustion(self, model, mode):
        #TODO: Do I really need to set STATE_NULL first?
        self.bin.set_state(self.gst.STATE_NULL)
        self.bin.set_state(self.gst.STATE_PLAYING)

class OSDNaggerNotifier(gobject.GObject):
    """A timer expiry notification view based on an unmanaged window."""
    def __init__(self, model):
        super(OSDNaggerNotifier, self).__init__()

        self.windows = {}

        display_manager = gtk.gdk.display_manager_get()
        for display in display_manager.list_displays():
            self.cb_display_opened(display_manager, display)

        model.connect('notify-tick', self.notify_exhaustion)
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

    def notify_exhaustion(self, model, mode):
        """Display an OSD on each monitor"""
        for win in self.windows.values():
            #TODO: The message template should be separated.
            #TODO: I need to also display some kind of message expiry countdown
            #XXX: Should I use a non-linear mapping for timeout?
            #FIXME: This doesn't yet get along with overtime.
            win.message("Timer Expired: %s" % mode.name,
                    abs(min(-5, mode.remaining() / 60)))

KNOWN_NOTIFY_MAP = {
        'audio': AudioNotifier,
        'libnotify': LibNotifyNotifier,
        'osd': OSDNaggerNotifier
}

#{ UI Components

class OSDWindow(RoundedWindow):
    """Simple OSD overlay for notifications"""

    font = pango.FontDescription("Sans Serif 22")

    def __init__(self, corner_radius=25, *args, **kwargs):
        super(OSDWindow, self).__init__(type=gtk.WINDOW_POPUP,
                corner_radius=corner_radius, *args, **kwargs)

        self.timeout_id = None

        self.set_border_width(10)
        self.label = gtk.Label()
        self.label.modify_font(self.font)
        self.add(self.label)

    def cb_timeout(self):
        self.timeout_id = None
        self.hide()
        return False

    def hide(self):
        if self.timeout_id:
            gobject.source_remove(self.timeout_id)
        super(OSDWindow, self).hide()

    def message(self, text, timeout):
        self.label.set_text(text)
        self.show_all()

        if self.timeout_id:
            gobject.source_remove(self.timeout_id)
        self.timeout_id = gobject.timeout_add_seconds(
                            int(timeout), self.cb_timeout)


#}

KNOWN_UI_MAP = {
        'compact': MainWinCompact,
        'legacy': TimeClock
}

def main():
    from optparse import OptionParser
    parser = OptionParser(version="%%prog v%s" % __version__)
    parser.add_option('-m', '--initial-mode', action="store", dest="mode",
                      default="Asleep", metavar="MODE",
                      help="start in MODE. (Use 'help' for a list)")
    parser.add_option('--ui',
                      action="append", dest="interfaces", default=[],
                      type='choice', choices=KNOWN_UI_MAP.keys(),
                      metavar="NAME",
                      help="Launch the specified UI instead of the default. "
                      "May be specified multiple times for multiple UIs.")
    parser.add_option('--notifier',
                      action="append", dest="notifiers", default=[],
                      type='choice', choices=KNOWN_NOTIFY_MAP.keys(),
                      metavar="NAME",
                      help="Activate the specified notification method. "
                      "May be specified several times for multiple notifiers.")
    parser.add_option('--develop',
                      action="store_true", dest="develop", default=False,
                      help="Use separate data store and single instance lock"
                      "so a development copy can be launched without "
                      "interfering with normal use")

    opts, args = parser.parse_args()

    if opts.develop:
        lockname = __file__ + '.dev'
        savefile = SAVE_FILE + '.dev'
    else:
        lockname, savefile = None, SAVE_FILE

    keepalive = []
    keepalive.append(SingleInstance(lockname=lockname))
    # This two-line definition shuts PyFlakes up about "assigned but not used"
    # Stuff beyond this point only runs if no other instance is already running

    gtkexcepthook.enable()

    # Model
    model = TimerModel(opts.mode, save_file=savefile)

    if opts.mode == 'help':
        print "Valid mode names are: %s" % ', '.join(model.timers)
        parser.exit(0)
    elif (opts.mode not in [x.name for x in model.timers]):
        default = model.timers[0]
        print ("Mode '%s' not recognized, defaulting to %s." %
            (opts.mode, default.name))
        opts.mode = default

    # Controllers
    TimerController(model)
    IdleController(model)

    # Notification Views
    if not opts.notifiers:
        opts.notifiers = DEFAULT_NOTIFY_LIST
    for name in opts.notifiers:
        try:
            KNOWN_NOTIFY_MAP[name](model)
        except ImportError:
            logging.warn("Could not initialize notifier %s due to unsatisfied "
                         "dependencies.", name)
        else:
            logging.info("Successfully instantiated notifier: %s", name)

    # UI Views
    if not opts.interfaces:
        opts.interfaces = DEFAULT_UI_LIST
    for name in opts.interfaces:
        try:
            KNOWN_UI_MAP[name](model)
        except ImportError:
            logging.warn("Could not initialize UI %s due to unsatisfied "
                         "dependencies.", name)
        else:
            logging.info("Successfully instantiated UI: %s", name)

    #TODO: Split out the PyNotify parts into a separate view(?) module.
    #TODO: Write up an audio notification view(?) module.
    #TODO: Try adding a "set urgent hint" call on the same interval as these.

    # Save state on exit
    sys.exitfunc = model.save

    # Make sure signals call sys.exitfunc.
    for signame in ("SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT"):
        sigconst = getattr(signal, signame, None)
        if sigconst:
            signal.signal(sigconst, lambda signum, stack_frame: sys.exit(0))

    # Make sure sys.exitfunc gets called on Ctrl+C
    try:
        gtk.main()  # TODO: Find some way to hook a lost X11 connection too.
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()

# vi:ts=4:sts=4:sw=4
