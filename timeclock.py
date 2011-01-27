#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple application to help lazy procrastinators (me) to manage their time.
See http://ssokolow.github.com/timeclock/ for a screenshot.

@todo: Planned improvements:
 - Decide how overflow should behave if the target timer is out too.
 - Double-check that it still works on Python 2.4.
 - Fixing setting up a decent MVC-ish archtecture using GObject signals.
   http://stackoverflow.com/questions/2057921/python-gtk-create-custom-signals
 - Clicking the preferences button while the dialog is shown shouldn't reset the
   unsaved preference changes.
 - Rework single-instance exclusion to ensure it's per-user. (Scope it the same
   as the DB)
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

@todo: Notification TODO:
 - Provide a fallback for when libnotify notifications are unavailable.
   (eg. Windows and Slax LiveCD/LiveUSB desktops)
 - Offer to turn the timer text a user-specified color (default: red) when it
   goes into negative values.
 - Finish the preferences page.
 - Add optional sound effects for timer completion using gst-python or PyGame:
   - http://mail.python.org/pipermail/python-list/2006-October/582445.html
   - http://www.jonobacon.org/2006/08/28/getting-started-with-gstreamer-with-python/
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

import gtk, gobject
import gtk.glade

import gtkexcepthook
gtkexcepthook.enable()

def get_icon_path(size):
    return os.path.join(SELF_DIR, "icons", "timeclock_%dx%d.png" % (size, size))

try:
    import pynotify
    from xml.sax.saxutils import escape as xmlescape
except ImportError:
    have_pynotify = False
else:
    have_pynotify = True
    pynotify.init(__appname__)

try:
    import gst
except ImportError:
    have_gstreamer = False
else:
    have_gstreamer = True
    # TODO: Complete GStreamer support.
    #uri = "file:///usr/share/sounds/KDE-Im-Nudge.ogg"
    #bin = gst.element_factory_make("playbin")
    #bin.set_property("uri", uri)
    #bin.set_state(gst.STATE_NULL)
    #bin.set_state(gst.STATE_PLAYING)

#TODO: Fall back to using winsound or wave and ossaudiodev
#TODO: Look into writing a generic wrapper which also tries things like these:
# - http://stackoverflow.com/questions/276266/whats-a-cross-platform-way-to-play-a-sound-file-in-python
# - http://stackoverflow.com/questions/307305/play-a-sound-with-python

class SingleInstance:
    """http://stackoverflow.com/questions/380870/python-single-instance-of-program/1265445#1265445"""
    def __init__(self):
        import sys as _sys    # Alias to please pyflakes
        self.lockfile = os.path.normpath(tempfile.gettempdir() + '/' + os.path.basename(__file__) + '.lock')
        self.platform = sys.platform  # Avoid an AttributeError in __del__
        if self.platform == 'win32':
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
me = SingleInstance()

CURRENT_SAVE_VERSION = 6 #: Used for save file versioning
class TimerModel(gobject.GObject):
    """
    Model+Controller class which will be further divided as part of
    re-architecting timeclock to be a properly modular MVC application.
    """
    __gsignals__ = {
        'mode-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (str, )),
        'tick': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (str, float))
    }

    def __init__(self, app, start_mode=None):
        self.__gobject_init__()

        self.last_tick = time.time()
        self.last_save = 0

        self.notify = True
        self.timer_order = [x['name'] for x in default_timers]
        self.timers = dict((x['name'], x) for x in default_timers)
        self.mode = self.timers.get(start_mode, None)

        # Make the notifications in advance,
        if have_pynotify:
            self.notifications = {}
            for mode in self.timers:
                notification = pynotify.Notification(
                    "%s Time Exhausted" % mode,
                    "You have used up your alotted time for %s" % xmlescape(mode.lower()),
                    get_icon_path(48))
                notification.set_urgency(pynotify.URGENCY_NORMAL)
                notification.set_timeout(pynotify.EXPIRES_NEVER)
                notification.last_shown = 0
                self.notifications[mode] = notification

        #TODO: Remove the back-reference to the app ASAP.
        self.app = app

    def notify_exhaustion(self, mode):
        """Display a libnotify notification that the given timer has expired."""
        if have_pynotify:
            notification = self.notifications[mode['name']]
            now = time.time()
            if notification.last_shown + 900 < now:
                notification.last_shown = now
                notification.show()

    def reset(self):
        """Reset all timers to starting values"""
        for name in self.timers:
            self.timers[name]['used'] = 0
            self.emit('tick', None, 0)
        self.set_active(None)

    def load(self):
        """Load the save file if present. Log and start clean otherwise."""
        if file_exists(SAVE_FILE):
            try:
                # Load the data, but leave the internal state unchanged in case
                # of corruption.

                # Don't rely on CPython's refcounting or Python 2.5's "with"
                fh = open(SAVE_FILE, 'rb')
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
                    win_state = {}
                elif version == 2:
                    version, total, used = loaded
                    notify = True
                    win_state = {}
                elif version == 1:
                    version, total_old, used_old = loaded
                    translate = ["N/A", "btn_overheadMode", "btn_workMode",
                                 "btn_playMode"]
                    total = dict( (translate.index(key), value)
                                  for key, value in total_old.items() )
                    used = dict( (translate.index(key), value)
                                 for key, value in used_old.items() )
                    notify = True
                    win_state = {}
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
                # File loaded successfully, now we put the data in place.
                self.notify = notify
                self.app.saved_state = win_state
                #FIXME: Replace this with some kind of 'loaded' signal.

            self.timer_order = [x['name'] for x in timers]
            self.timers = dict((x['name'], x) for x in timers)
            self.emit('tick', None, 0)

    def remaining(self, mode=None):
        mode = mode or self.mode
        return mode['total'] - mode['used']

    def save(self):
        """Exit/Timeout handler for the app. Gets called every five minutes and
        on every type of clean exit except xkill. (PyGTK doesn't let you)

        Saves the current timer values to disk."""
        window_state = {
                 'position': self.app.win.get_position(),
                'decorated': self.app.win.get_decorated()
        }

        timers = []
        for name in self.timer_order:
            timers.append(self.timers[name])

        data = {
            'timers': timers,
            'notify': {'enable': self.notify},
            'window': window_state,
        }

        # Don't rely on CPython's refcounting or Python 2.5's "with"
        fh = open(SAVE_FILE + '.tmp', "wb")
        pickle.dump( (CURRENT_SAVE_VERSION, data), fh)
        fh.close()

        # Corruption from saving without atomic replace has been observed
        os.rename(SAVE_FILE + '.tmp', SAVE_FILE)
        self.last_save = time.time()
        return True

    def set_active(self, name):
        #XXX: Decide how to properly handle the Asleep case.
        self.mode = self.timers.get(name, None)
        self.emit('mode-changed', name)
        #TODO: Actually listen on this signal.

    def tick(self):
        """Callback for updating progress bars.

        :note: Emitted 'tick' signal is not exclusively for incrementing the
        the clock display. Examine how much time has actually elapsed.
        """
        now = time.time()
        if self.mode:
            delta = now - self.last_tick
            self.mode['used'] += delta

            if self.remaining() < 0:
                overtime = abs(self.remaining())
                overflow_to = self.timers.get(self.mode.get('overflow'))
                if overflow_to:
                    # TODO: Probably best to rethink to allow accurate
                    # record-keeping. (Maybe an additional field to track
                    # overflowed time so I can drain "total" rather than "used"
                    # without messing up stored settings)
                    overflow_to['used'] += overtime
                    # This works because overtime keeps getting reset to zero.

                #TODO: This should be more elegant (Probably make modes objects)
                if self.notify and overflow_to and self.remaining(overflow_to) < 0:
                    self.notify_exhaustion(overflow_to)
                else:
                    self.notify_exhaustion(self.mode)

                if overflow_to:
                    self.mode['used'] = self.mode['total']

                self.emit('tick', overflow_to['name'], overtime)

            #TODO: Rework overtime calculation so this is proper.
            self.emit('tick', self.mode['name'], delta)

            if now >= (self.last_save + SAVE_INTERVAL):
                self.save()

        self.last_tick = now

        return True

class ModeButton(gtk.RadioButton):
    def __init__(self, model, group=None, *args, **kwargs):
        gtk.RadioButton.__init__(self, *args, **kwargs)

        self.model = model
        self.mode = model.get('name', None)

        self.progress = gtk.ProgressBar()
        self.add(self.progress)

        self.set_mode(False)
        self.progress.set_fraction(1.0)
        self.update_label()

    def get_text(self):
        return self.progress.get_text()

    def update_label(self):
        remaining = round(self.model['total'] - self.model['used'])
        if remaining >= 0:
            ptime = time.strftime('%H:%M:%S', time.gmtime(remaining))
        else:
            ptime = time.strftime('-%H:%M:%S', time.gmtime(abs(remaining)))

        self.progress.set_text('%s: %s' % (self.model['name'], ptime))
        self.progress.set_fraction(max(float(remaining) / self.model['total'], 0))


class MainWin(gtk.Window):
    def __init__(self, timer):
        gtk.Window.__init__(self)
        self.set_icon_from_file(get_icon_path(64))

        self.timer = timer
        self.evbox = gtk.EventBox()
        self.box = gtk.HBox()
        self.btnbox = gtk.HButtonBox()

        self.btns = {}
        for name in self.timer.timer_order:
            btn = ModeButton(model=self.timer.timers[name])
            self.btns[name] = btn

            btn.connect('toggled', self.mode_changed)
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

        drag_handle = gtk.image_new_from_file(get_icon_path(22))

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
        self.evbox.connect('button-release-event', self.showMenu)
        # TODO: Make this work.
        #self.evbox.connect('popup-menu', self.showMenu)

        self.update(self.timer)
        self.show_all()

    def mode_changed(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.timer.set_active(widget.mode)

        if not widget.mode:
            self.timer.save()

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

        menu = gtk.Menu()

        asleep = gtk.RadioMenuItem(None, "_Asleep")
        reset = gtk.MenuItem("_Reset...")
        sep = gtk.SeparatorMenuItem()
        prefs = gtk.MenuItem("_Preferences...")
        quit = gtk.ImageMenuItem(stock_id="gtk-quit")
        menu.append(asleep)
        menu.append(reset)
        menu.append(sep)
        menu.append(prefs)
        menu.append(quit)

        menu.show_all()
        menu.popup(None, None, None, 3, evtTime)

        return True

class TimeClock(object):
    selectedBtn = None

    def __init__(self, start_mode="sleep"):

        #Set the Glade file
        self.mTree = gtk.glade.XML(os.path.join(SELF_DIR, "main_large.glade"))
        self.pTree = gtk.glade.XML(os.path.join(SELF_DIR, "preferences.glade"))

        self.timer = TimerModel(self, start_mode)
        self._init_widgets()

        # 'tick' must be connected before the load.
        self.timer.connect('tick', self.update_progressBars)
        self.saved_state = {}
        self.timer.load()

        # Connect signals
        mDic = { "on_mode_toggled"    : self.mode_changed,
                 "on_reset_clicked"   : self.reset_clicked,
                 "on_mainWin_destroy" : gtk.main_quit,
                 "on_prefs_clicked"   : self.prefs_clicked }
        pDic = { "on_prefs_commit"    : self.prefs_commit,
                 "on_prefs_cancel"    : self.prefs_cancel }
        self.mTree.signal_autoconnect(mDic)
        self.pTree.signal_autoconnect(pDic)
        gobject.timeout_add(1000, self.timer.tick)

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

    def mode_changed(self, widget):
        """Callback for clicking the timer-selection radio buttons"""
        if widget.get_active():
            self.selectedBtn = widget
            self.timer.set_active(widget.mode)

        if not self.selectedBtn.mode:
            self.timer.save()

    def reset_clicked(self, widget):
        """Callback for the reset button"""
        self.mTree.get_widget('btn_sleepMode').set_active(True)
        self.timer.reset()

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
        if have_pynotify:
            notify_box.set_sensitive(True)
            notify_box.set_label("display notifications")
        else:
            notify_box.set_sensitive(False)
            notify_box.set_label("display notifications (Requires pynotify)")

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

def main():
    from optparse import OptionParser
    parser = OptionParser(version="%%prog v%s" % __version__)
    parser.add_option('-m', '--initial-mode',
                      action="store", dest="mode", default="sleep",
                      metavar="MODE", help="start in MODE. (Use 'help' for a list)")

    opts, args = parser.parse_args()
    #FIXME: Restore this once the model is truly independent of the view.
    #if opts.mode == 'help':
    #    print "Valid mode names are: %s" % ', '.join(MODE_NAMES)
    #    parser.exit(0)
    #elif (opts.mode not in MODE_NAMES):
    #    print "Mode '%s' not recognized, defaulting to sleep." % opts.mode
    #    opts.mode = None
    app = TimeClock(start_mode=opts.mode)
    MainWin(app.timer)

    #TODO: Split out the PyNotify parts into a separate view(?) module.
    #TODO: Write up an audio notification view(?) module.
    #TODO: Explore adding a "set urgent hint" call on the same interval as these.

    # Save state on exit
    sys.exitfunc = app.timer.save

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
