#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.
See http://ssokolow.github.com/timeclock/ for a screenshot.

@todo: Update site to reflect PyGTK 2.8 being required for PyCairo.

@todo: Planned improvements:
 - Split "mode" into "selected" and "active" for a generalized version of the
   (pressed button vs. title displayed in taskbar) distinction.
 - Make my API for getters and setters use property() instead.
 - Decide how overflow should behave if the target timer is out too.
 - Double-check that it still works on Python 2.4.
 - Fixing setting up a decent MVC-ish archtecture using GObject signals.
   http://stackoverflow.com/questions/2057921/python-gtk-create-custom-signals
 - Clicking the preferences button while the dialog is shown shouldn't reset the
   unsaved preference changes.
 - Extend the single-instance system to use D-Bus if available to raise/focus the
   existing instance if one is already running.
 - Figure out some intuitive, non-distracting way to allow the user to make
   corrections. (eg. if you forget to set the timer to leisure before going AFK)
 - Should I offer preferences options for remembering window position and things
   like "always on top" and "on all desktops"?
 - Have the system complain if overhead + work + leisure + sleep (8 hours) > 24
   and enforce minimums of 1 hour for leisure and overhead.
 - Rework the design to minimize dependence on GTK+ (in case I switch to Qt for
   Phonon)
 - Report PyGTK's uncatchable xkill response on the bug tracker.
 - Explore how progress bars behave when their base colors are changed:
   (http://hg.atheme.org/audacious/audacious-plugins/diff/a25b618e8f4a/src/gtkui/ui_playlist_widget.c)

@todo: Optionally use idle detection to auto-trigger Overhead on wake
 - http://www.xfree86.org/current/Xss.3.html (xpyb. python-xlib has no XSS ext. wrapper)
   - Poll with xcb.get_file_descriptor and GTK's select handler.
 - http://msdn.microsoft.com/en-us/library/ms646302.aspx (pywin32?)
 - http://stackoverflow.com/questions/608710/monitoring-user-idle-time
 - Probably a good idea to write and share a wrapper

@todo: Notification TODO:
 - Provide a fallback for when libnotify notifications are unavailable.
   (eg. Windows and Slax LiveCD/LiveUSB desktops)
 - Offer to turn the timer text a user-specified color (default: red) when it
   goes into negative values.
 - Finish the preferences page.
 - Set up a callback for timer exhaustion.
 - Handle popup notifications more intelligently (eg. Explicitly hide them when
   switching away from an expired timer and explicitly show them when switching
   to one)

@todo: Consider:
 - Changing this into a Plasma widget (Without dropping PyGTK support)
 - Using PyKDE's bindings to the KDE Notification system (for the Plasma widget)
 - Look into integrating with http://projecthamster.wordpress.com/

@todo: Publish this on listing sites:
 - http://gtk-apps.org/
 - http://pypi.python.org/pypi

@newfield appname: Application Name
"""

__appname__ = "The Procrastinator's Timeclock"
__authors__  = ["Stephan Sokolow (deitarion/SSokolow)", "Charlie Nolan (FunnyMan3595)"]
__version__ = "0.2.99.0"
__license__ = "GNU GPL 2.0 or later"

default_timers = [
    {
        'name' : 'Overhead',
        'total': int(3600 * 3.5),
        'used' : 0,
        'overflow': 'Leisure'
    },
    {
        'name' : 'Work',
        'total': int(3600 * 6.0),
        'used' : 0,
    },
    {
        'name' : 'Leisure',
        'total': int(3600 * 5.5),
        'used' : 0,
    }
]

import copy, logging, os, signal, sys, tempfile, time, pickle

SELF_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
if not os.path.isdir(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except OSError:
        raise SystemExit("Aborting: %s exists but is not a directory!"
                               % DATA_DIR)
SAVE_FILE = os.path.join(DATA_DIR, "timeclock.sav")
SAVE_INTERVAL = 60 * 5  # 5 Minutes
NOTIFY_INTERVAL = 60 * 15 # 15 Minutes
NOTIFY_SOUND = os.path.join(os.path.dirname(os.path.realpath(__file__)), '49213__tombola__Fisher_Price29.wav')
DEFAULT_UI_LIST = ['compact', 'legacy']
DEFAULT_NOTIFY_LIST = ['audio', 'libnotify']
file_exists = os.path.isfile

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

#TODO: What was I trying to do here?
# (I get the feeling this try/except neutralizes every use of pygtk.require
# except switching between different available versions)
try:
    import pygtk
    pygtk.require("2.0")
except:
    pass

import cairo, gtk, gobject
import gtk.glade

import gtkexcepthook

# Known generated icon sizes.
ICON_SIZES = [16,22,32,48,64]
def get_icon_path(size):
    for icon_size in sorted(ICON_SIZES, reverse=True):
        if icon_size <= size:
            size = icon_size
            break

    return os.path.join(SELF_DIR, "icons", "timeclock_%dx%d.png" % (size, size))

class SingleInstance:
    """http://stackoverflow.com/questions/380870/python-single-instance-of-program/1265445#1265445"""
    def __init__(self, useronly=True, lockfile=None, lockname=None):
        """
        :param useronly: Allow one instance per user rather than one instance overall.
            (On Windows, this is always True)
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
                base = os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
                self.lockfile = os.path.join(base, fname)

                if not os.path.exists(base):
                    os.makedirs(base)

        self.lockfile = os.path.normpath(os.path.normcase(self.lockfile))

        if self.platform == 'win32': #TODO: What about Win64? os.name == 'nt'?
                try:
                        # file already exists, we try to remove (in case previous execution was interrupted)
                        if(os.path.exists(self.lockfile)):
                                os.unlink(self.lockfile)
                        self.fd =  os.open(self.lockfile, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                except OSError, e:
                        if e.errno == 13:
                                print "Another instance is already running, quitting."
                                _sys.exit(-1)
                        print e.errno
                        raise
        else: # non Windows
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

CURRENT_SAVE_VERSION = 6 #: Used for save file versioning
class TimerModel(gobject.GObject):
    """Model class which still needs more refactoring."""
    __gsignals__ = {
        'mode-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (str, )),
        'tick': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (str, float))
    }

    def __init__(self, start_mode=None, save_file=SAVE_FILE):
        self.__gobject_init__()

        self.last_save = 0
        self.save_file = save_file

        self.notify = True
        self.timer_order = [x['name'] for x in default_timers]
        self.timers = dict((x['name'], x) for x in default_timers)
        self.mode = self.timers.get(start_mode, None)

    def reset(self):
        """Reset all timers to starting values"""
        for name in self.timers:
            self.timers[name]['used'] = 0
            self.emit('tick', None, 0)
        self.set_active(None)

    def load(self):
        """Load the save file if present. Log and start clean otherwise."""
        if file_exists(self.save_file):
            try:
                # Load the data, but leave the internal state unchanged in case
                # of corruption.

                # Don't rely on CPython's refcounting or Python 2.5's "with"
                fh = open(self.save_file, 'rb')
                loaded = pickle.load(fh)
                fh.close()

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
                        _ohead['overflow'] =  'Leisure'
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
                    total = dict( (translate.index(key), value)
                                  for key, value in total_old.items() )
                    used = dict( (translate.index(key), value)
                                 for key, value in used_old.items() )
                    notify = True
                    #win_state = {}
                else:
                    raise ValueError("Save file too new! (Expected %s, got %s)" % (CURRENT_SAVE_VERSION, version))

                if version <= 4:
                    SLEEP, OVERHEAD, WORK, LEISURE = range(4)
                    MODE_NAMES = (None, 'Overhead', 'Work', 'Leisure')

                    timers = []
                    for pos, row in enumerate(zip(total, used)):
                        timers.append({
                            'name' : MODE_NAMES[pos],
                            'total': row[0],
                            'used' : row[1],
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

            self.timer_order = [x['name'] for x in timers]
            self.timers = dict((x['name'], x) for x in timers)
            self.emit('tick', None, 0)

    def remaining(self, mode=None):
        mode = mode or self.mode
        if not mode: #TODO: Make modes objects so I can do this properly.
            return 0
        return mode['total'] - mode['used']

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

        timers = []
        for name in self.timer_order:
            timers.append(self.timers[name])

        data = {
            'timers': timers,
            'notify': {'enable': self.notify},
            'window': window_state,
        }

        # Don't rely on CPython's refcounting or Python 2.5's "with"
        fh = open(self.save_file + '.tmp', "wb")
        pickle.dump( (CURRENT_SAVE_VERSION, data), fh)
        fh.close()

        # Corruption from saving without atomic replace has been observed
        os.rename(self.save_file + '.tmp', self.save_file)
        self.last_save = time.time()
        return True

    def get_active(self):
        return self.mode

    def set_active(self, name):
        #XXX: Decide how to properly handle the Asleep case.
        self.mode = self.timers.get(name, None)
        self.emit('mode-changed', name)
        #TODO: Actually listen on this signal.

#{ Controller Modules

class TimerController(gobject.GObject):
    """The default timer behaviour for the timeclock."""
    def __init__(self, model):
        self.__gobject_init__()

        self.model = model
        self.last_tick = time.time()
        gobject.timeout_add(1000, self.tick)

    def tick(self):
        """Callback for updating progress bars.

        :note: Emitted 'tick' signal is not exclusively for incrementing the
        the clock display. Examine how much time has actually elapsed.
        """
        now, mode = time.time(), self.model.get_active()
        if mode:
            delta = now - self.last_tick
            self.model.mode['used'] += delta

            if self.model.remaining() < 0:
                overtime = abs(self.model.remaining())
                overflow_to = self.model.timers.get(self.model.mode.get('overflow'))
                if overflow_to:
                    # TODO: Probably best to rethink to allow accurate
                    # record-keeping. (Maybe an additional field to track
                    # overflowed time so I can drain "total" rather than "used"
                    # without messing up stored settings)
                    overflow_to['used'] += overtime
                    # This works because overtime keeps getting reset to zero.

                if overflow_to:
                    self.model.mode['used'] = self.model.mode['total']
                    self.model.emit('tick', overflow_to['name'], overtime)

            #TODO: Rework overtime calculation so this is proper.
            self.model.emit('tick', self.model.mode['name'], delta)

            if now >= (self.model.last_save + SAVE_INTERVAL):
                self.model.save()

        self.last_tick = now
        return True


class IdleController(gobject.GObject):
    """A controller to set and unset Asleep automatically."""
    def __init__(self, model):
        self.__gobject_init__()
        pass #TODO: Implement

#{ Notification Modules

class LibNotifyNotifier(gobject.GObject):
    """A timer expiry notification view based on libnotify.

    :todo: Redesign this on an abstraction over Growl, libnotify, and toasts.
    """
    pynotify = None

    def __init__(self, model):
        # ImportError should be caught when instantiating this.
        import pynotify
        from xml.sax.saxutils import escape as xmlescape

        # Do this second because I'm unfamiliar with GObject refcounting.
        self.__gobject_init__()

        # Only init PyNotify once
        if not self.pynotify:
            pynotify.init(__appname__)
            self.__class__.pynotify = pynotify

        # Make the notifications in advance,
        self.last_notified = 0
        self.notifications = {}
        for mode in model.timers:
            notification = pynotify.Notification(
                "%s Time Exhausted" % mode,
                "You have used all allotted time for %s" % xmlescape(mode.lower()),
                get_icon_path(48))
            notification.set_urgency(pynotify.URGENCY_NORMAL)
            notification.set_timeout(pynotify.EXPIRES_NEVER)
            notification.last_shown = 0
            self.notifications[mode] = notification

        model.connect('tick', self.tick)

    def tick(self, model, mode, delta):
        #TODO: This should be more elegant (Probably make modes objects)
        if not model.mode: #TODO: Make modes objects so I can do this properly.
            return
        if model.remaining() > 0:
            return
        else:
            overflow_to = model.timers.get(model.mode.get('overflow'))
            if overflow_to and model.remaining(overflow_to) <= 0:
                self.notify_exhaustion(overflow_to)
            elif model.remaining() <= 0:
                self.notify_exhaustion(model.mode)

    def notify_exhaustion(self, mode):
        """Display a libnotify notification that the given timer has expired."""
        #TODO: Probably more elegant to put the time check in tick()
        notification = self.notifications[mode['name']]
        now = time.time()
        if notification.last_shown + 900 < now:
            notification.last_shown = now
            notification.show()

class AudioNotifier(gobject.GObject):
    """An auditory timer expiry notification based on a portability layer."""
    def __init__(self, model):
        # Keep "import gst" from grabbing --help, printing its own help, and exiting
        _argv, sys.argv = sys.argv, []

        try:
            import gst
            import urllib
        finally:
            # Restore sys.argv so I can parse it cleanly.
            # XXX: Use a context manager once I decide to drop Python 2.4 support.
            sys.argv = _argv
            del _argv

        self.gst = gst
        self.__gobject_init__()

        self.last_notified = 0
        self.uri = NOTIFY_SOUND

        if os.path.exists(self.uri):
            self.uri = 'file://' + urllib.pathname2url(os.path.abspath(self.uri))
        self.bin = gst.element_factory_make("playbin")
        self.bin.set_property("uri", self.uri)

        if model:
            model.connect('tick', self.tick)

        #TODO: Fall back to using winsound or wave and ossaudiodev or maybe pygame
        #TODO: Design a generic wrapper which also tries things like these:
        # - http://stackoverflow.com/questions/276266/whats-a-cross-platform-way-to-play-a-sound-file-in-python
        # - http://stackoverflow.com/questions/307305/play-a-sound-with-python

    def tick(self, model, mode, delta):
        if not model.mode: #TODO: Make modes objects so I can do this properly.
            return
        now = time.time()
        if model.remaining() <= 0 and self.last_notified + 900 < now:
            #TODO: Did I really need to do this?
            self.bin.set_state(self.gst.STATE_NULL)
            self.bin.set_state(self.gst.STATE_PLAYING)
            self.last_notified = now

KNOWN_NOTIFY_MAP = {
        'audio': AudioNotifier,
        'libnotify': LibNotifyNotifier
}

#{ UI Components

class RoundedWindow(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.connect('size-allocate', self._on_size_allocate)
        self.set_decorated(False)

    def rounded_rectangle(self, cr, x, y, w, h, r=20):
        """Draw a rounded rectangle using Cairo.
        Source: http://stackoverflow.com/questions/2384374/rounded-rectangle-in-pygtk

        This is just one of the samples from
        http://www.cairographics.org/cookbook/roundedrectangles/
          A****BQ
         H      C
         *      *
         G      D
          F****E
        """

        cr.move_to(x+r,y)                      # Move to A
        cr.line_to(x+w-r,y)                    # Straight line to B
        cr.curve_to(x+w,y,x+w,y,x+w,y+r)       # Curve to C, Control points are both at Q
        cr.line_to(x+w,y+h-r)                  # Move to D
        cr.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h) # Curve to E
        cr.line_to(x+r,y+h)                    # Line to F
        cr.curve_to(x,y+h,x,y+h,x,y+h-r)       # Curve to G
        cr.line_to(x,y+r)                      # Line to H
        cr.curve_to(x,y,x,y,x+r,y)             # Curve to A

    def _on_size_allocate(self, win, allocation):
        w,h = allocation.width, allocation.height
        bitmap = gtk.gdk.Pixmap(None, w, h, 1)
        cr = bitmap.cairo_create()

        # Clear the bitmap
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()

        # Draw our shape into the bitmap using cairo
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        self.rounded_rectangle(cr, 0, 0, w, h, 10)
        cr.fill()

        # Set the window shape
        win.shape_combine_mask(bitmap, 0, 0)

class ModeButton(gtk.RadioButton):
    def __init__(self, model, name, group=None, *args, **kwargs):
        super(ModeButton, self).__init__(*args, **kwargs)

        self.model = model
        self.mode = name

        self.progress = gtk.ProgressBar()
        self.add(self.progress)

        self.set_mode(False)
        self.progress.set_fraction(1.0)
        self.update_label()

    def get_text(self):
        return self.progress.get_text()

    def update_label(self):
        model = self.model.timers[self.mode]
        remaining = round(model['total'] - model['used'])
        if remaining >= 0:
            ptime = time.strftime('%H:%M:%S', time.gmtime(remaining))
        else:
            ptime = time.strftime('-%H:%M:%S', time.gmtime(abs(remaining)))

        self.progress.set_text('%s: %s' % (model['name'], ptime))
        self.progress.set_fraction(max(float(remaining) / model['total'], 0))

class MainWinContextMenu(gtk.Menu):
    def __init__(self, model, *args, **kwargs):
        super(MainWinContextMenu, self).__init__(*args, **kwargs)
        self.model = model

        asleep = gtk.RadioMenuItem(None, "_Asleep")
        reset = gtk.MenuItem("_Reset...")
        sep = gtk.SeparatorMenuItem()
        prefs = gtk.MenuItem("_Preferences...")
        quit = gtk.ImageMenuItem(stock_id="gtk-quit")

        self.append(asleep)
        self.append(reset)
        self.append(sep)
        self.append(prefs)
        self.append(quit)

        #TODO: asleep
        reset.connect('activate', self.cb_reset)
        #TODO: prefs
        quit.connect('activate', gtk.main_quit)

    def cb_reset(self, widget):
        #TODO: Look into how to get MainWin via parent-lookup calls so this can be destroyed with its parent.
        confirm = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Reset all timers?\n"
                "Warning: This operation cannot be undone.")
        if confirm.run() == gtk.RESPONSE_OK:
            self.model.reset()
        confirm.destroy()

class MainWin(RoundedWindow):
    def __init__(self, timer):
        super(MainWin, self).__init__()
        self.set_icon_from_file(get_icon_path(64))

        self.timer = timer
        self.evbox = gtk.EventBox()
        self.box = gtk.HBox()
        self.btnbox = gtk.HButtonBox()
        self.menu = MainWinContextMenu(timer)

        self.btns = {}
        for name in self.timer.timer_order:
            btn = ModeButton(model=self.timer, name=name)
            self.btns[name] = btn

            btn.connect('toggled', self.btn_toggled)
            btn.connect('button-press-event', self.showMenu)
            self.btnbox.add(btn)

        # RadioMenuItem can't share a group with RadioButton
        # ...so we fake it using hidden group members and signals.
        sleep_btn = gtk.RadioButton()
        sleep_btn.set_label('Asleep')
        #TODO: Hook up signals to share state with RadioMenuItem

        for name in self.btns:
            self.btns[name].set_group(sleep_btn)
        self.btns[None] = sleep_btn

        drag_handle = gtk.Image()

        self.box.add(drag_handle)
        self.box.add(self.btnbox)

        self.evbox.add(self.box)
        self.add(self.evbox)
        self.set_decorated(False)
        #TODO: See if I can achieve something suitable using a window type too.

        # Because window-state-event is broken on many WMs, default to sticky,
        # on top as a most likely default for users. (TODO: Preferences toggle)
        self.set_keep_above(True)
        self.stick()

        self.timer.connect('tick', self.update)
        self.timer.connect('mode-changed', self.mode_changed)
        self.evbox.connect('button-release-event', self.showMenu)
        # TODO: Make this work.
        #self.evbox.connect('popup-menu', self.showMenu)

        self.update(self.timer)
        self.menu.show_all() #TODO: Is this line necessary?
        self.show_all()

        # Set the icon after we know how much vert space the GTK+ theme gives us.
        drag_handle.set_from_file(get_icon_path(drag_handle.get_allocation()[3]))

    #TODO: Normalize callback naming
    def btn_toggled(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.timer.set_active(widget.mode)

        if not widget.mode:
            self.timer.save()

    def mode_changed(self, model, mode=None):
        btn = self.btns.get(mode)
        if btn and not btn.get_active():
            btn.set_active(True)

    def update(self, timer, mode=None, delta=None):
        """Common code used for initializing and updating the progress bars.

        :todo: Actually use the mode and delta passed in.
        """
        for name in self.btns:
            if name: # Exclude "Asleep"
                self.btns[name].update_label()
        if self.timer.mode:
            #FIXME: Not helpful when overflow kicks in. Rethink.
            # (Maybe fixable with my "don't actually make overflow reset the
            # active timer" change for record-keeping.)
            self.set_title(self.btns[self.timer.mode['name']].get_text())
        else:
            self.set_title("Timeclock Paused")

    def showMenu(self, widget, event=None, data=None):
        if event:
            evtBtn, evtTime = event.button, event.get_time()

            if evtBtn != 3:
                return False
        else:
            evtBtn, evtTime = None, None

        self.menu.popup(None, None, None, 3, evtTime)

        return True

#}

class TimeClock(object):
    selectedBtn = None

    def __init__(self, timer):

        #Set the Glade file
        self.mTree = gtk.glade.XML(os.path.join(SELF_DIR, "main_large.glade"))
        self.pTree = gtk.glade.XML(os.path.join(SELF_DIR, "preferences.glade"))

        self.timer = timer
        self._init_widgets()

        # 'tick' must be connected before the load.
        self.timer.connect('tick', self.update_progressBars)
        self.timer.connect('mode-changed', self.mode_changed)
        self.saved_state = {}

        # Connect signals
        mDic = { "on_mode_toggled"    : self.btn_toggled,
                 "on_reset_clicked"   : self.cb_reset,
                 "on_mainWin_destroy" : gtk.main_quit,
                 "on_prefs_clicked"   : self.prefs_clicked }
        pDic = { "on_prefs_commit"    : self.prefs_commit,
                 "on_prefs_cancel"    : self.prefs_cancel }
        self.mTree.signal_autoconnect(mDic)
        self.pTree.signal_autoconnect(pDic)

        # -- Restore saved window state when possible --

        # Because window-state-event is broken on many WMs, default to sticky,
        # on top as a most likely default for users. (TODO: Preferences toggle)
        self.win = self.mTree.get_widget('mainWin')
        self.win.set_keep_above(True)
        self.win.stick()

        # Restore the saved window state if present
        position = self.saved_state.get('position', None)
        if position is not None:
            self.win.move(*position)
        decorated = self.saved_state.get('decorated', None)
        if decorated is not None:
            self.win.set_decorated(decorated)

    def _init_widgets(self):
        """All non-signal, non-glade widget initialization."""
        # Set up the data structures
        self.timer_widgets = {}
        for mode in self.timer.timers:
            widget = self.mTree.get_widget('btn_%sMode' % mode.lower())
            widget.mode = mode
            self.timer_widgets[widget] = \
                self.mTree.get_widget('progress_%sMode' % mode.lower())
        sleepBtn = self.mTree.get_widget('btn_sleepMode')
        sleepBtn.mode = None

        if self.timer.mode:
            self.selectedBtn = self.mTree.get_widget('btn_%sMode' % self.timer.mode.name.lower())
        else:
            self.selectedBtn = sleepBtn
        self.selectedBtn.set_active(True)

        # Because PyGTK isn't reliably obeying Glade
        self.update_progressBars()
        for widget in self.timer_widgets:
            widget.set_property('draw-indicator', False)
        sleepBtn.set_property('draw-indicator', False)

    def cb_reset(self, widget):
        #TODO: Look into how to get MainWin via parent-lookup calls so this can be destroyed with its parent.
        confirm = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Reset all timers?\n"
                "Warning: This operation cannot be undone.")
        if confirm.run() == gtk.RESPONSE_OK:
            self.timer.reset()
        confirm.destroy()

    def update_progressBars(self, timer=None, mode=None, delta=None):
        """Common code used for initializing and updating the progress bars.

        :todo: Actually use the values passed in by the emit() call.
        """
        for widget in self.timer_widgets:
            timer = self.timer.timers[widget.mode]
            pbar = self.timer_widgets[widget]
            total, val = timer['total'], timer['used']
            remaining = round(total - val)
            if pbar:
                if remaining >= 0:
                    pbar.set_text(time.strftime('%H:%M:%S', time.gmtime(remaining)))
                else:
                    pbar.set_text(time.strftime('-%H:%M:%S', time.gmtime(abs(remaining))))
                pbar.set_fraction(max(float(remaining) / timer['total'], 0))

    def btn_toggled(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget
            self.timer.set_active(widget.mode)

        if not self.selectedBtn.mode:
            self.timer.save()

    def mode_changed(self, model, mode=None):
        mode = mode or 'sleep'
        btn = self.mTree.get_widget('btn_%sMode' % mode.lower())
        if btn and not btn.get_active():
            btn.set_active(True)

    def prefs_clicked(self, widget):
        """Callback for the preferences button"""
        # Set the spin widgets to the current settings.
        for mode in self.timer.total:
            widget_spin =  'spinBtn_%sMode' % mode.lower()
            widget = self.pTree.get_widget(widget_spin)
            widget.set_value(self.timer.total[mode] / 3600.0)

        # Set the notify option to the current value, disable and explain if
        # pynotify is not installed.
        notify_box = self.pTree.get_widget('checkbutton_notify')
        notify_box.set_active(self.timer.notify)
        notify_box.set_sensitive(True)
        notify_box.set_label("display notifications")

        self.pTree.get_widget('prefsDlg').show()

    def prefs_cancel(self, widget):
        """Callback for cancelling changes the preferences"""
        self.pTree.get_widget('prefsDlg').hide()

    def prefs_commit(self, widget):
        """Callback for OKing changes to the preferences"""
        # Update the time settings for each mode.
        for mode in self.timer.total:
            widget_spin =  'spinBtn_%sMode' % mode.lower()
            widget = self.pTree.get_widget(widget_spin)
            self.timer.total[mode] = (widget.get_value() * 3600)

        notify_box = self.pTree.get_widget('checkbutton_notify')
        self.timer.notify = notify_box.get_active()

        # Remaining cleanup.
        self.update_progressBars()
        self.pTree.get_widget('prefsDlg').hide()

KNOWN_UI_MAP = {
        'compact': MainWin,
        'legacy': TimeClock
}

def main():
    from optparse import OptionParser
    parser = OptionParser(version="%%prog v%s" % __version__)
    parser.add_option('-m', '--initial-mode',
                      action="store", dest="mode", default="sleep",
                      metavar="MODE", help="start in MODE. (Use 'help' for a list)")
    parser.add_option('--ui',
                      action="append", dest="interfaces", default=[],
                      type='choice', choices=KNOWN_UI_MAP.keys(), metavar="NAME",
                      help="Launch the specified UI instead of the default. "
                      "May be specified multiple times for multiple UIs.")
    parser.add_option('--notifier',
                      action="append", dest="notifiers", default=[],
                      type='choice', choices=KNOWN_NOTIFY_MAP.keys(), metavar="NAME",
                      help="Activate the specified notification method. "
                      "May be specified multiple times for multiple notifiers.")
    parser.add_option('--develop',
                      action="store_true", dest="develop", default=False,
                      help="Use separate data store and single instance lock"
                      "so a development copy can be launched without "
                      "interfering with normal use")

    opts, args = parser.parse_args()
    #FIXME: Restore this once the model is truly independent of the view.
    #if opts.mode == 'help':
    #    print "Valid mode names are: %s" % ', '.join(MODE_NAMES)
    #    parser.exit(0)
    #elif (opts.mode not in MODE_NAMES):
    #    print "Mode '%s' not recognized, defaulting to sleep." % opts.mode
    #    opts.mode = None

    if opts.develop:
        lockname = __file__ + '.dev'
        savefile = SAVE_FILE + '.dev'
    else:
        lockname, savefile = None, SAVE_FILE

    keepalive = []
    keepalive.append(SingleInstance(lockname=lockname))
    # This two-line definition shuts PyFlakes up about "assigned but never used"
    # Stuff beyond this point only runs if no other instance is already running.

    gtkexcepthook.enable()

    # Model
    timer = TimerModel(opts.mode, save_file=savefile)
    timer.load()

    # Controllers
    TimerController(timer)

    # Notification Views
    if not opts.notifiers:
        opts.notifiers = DEFAULT_NOTIFY_LIST
    for name in opts.notifiers:
        try:
            KNOWN_NOTIFY_MAP[name](timer)
        except ImportError:
            logging.warn("Could not initialize notifier %s due to unsatisfied dependencies.", name)
        else:
            logging.info("Successfully instantiated notifier: %s", name)

    # UI Views
    if not opts.interfaces:
        opts.interfaces = DEFAULT_UI_LIST
    for name in opts.interfaces:
        try:
            KNOWN_UI_MAP[name](timer)
        except ImportError:
            logging.warn("Could not initialize UI %s due to unsatisfied dependencies.", name)
        else:
            logging.info("Successfully instantiated UI: %s", name)

    #TODO: Split out the PyNotify parts into a separate view(?) module.
    #TODO: Write up an audio notification view(?) module.
    #TODO: Explore adding a "set urgent hint" call on the same interval as these.

    # Save state on exit
    sys.exitfunc = timer.save

    # Make sure signals call sys.exitfunc.
    for signame in ("SIGTERM", "SIGINT", "SIGHUP", "SIGQUIT"):
        sigconst = getattr(signal, signame, None)
        if sigconst:
            signal.signal(sigconst, lambda signum, stack_frame: sys.exit(0))

    # Make sure sys.exitfunc gets called on Ctrl+C
    try:
        gtk.main() # TODO: Find some way to hook a lost X11 connection too.
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    main()

# vi:ts=4:sts=4:sw=4
