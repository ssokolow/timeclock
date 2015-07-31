"""Data model and save/load code"""
from __future__ import absolute_import

__authors__ = [
    "Stephan Sokolow (deitarion/SSokolow)",
    "Charlie Nolan (FunnyMan3595)"]
__author__ = ', '.join(__authors__)
__license__ = "GNU GPU 2.0 or later"

import copy, logging, os, time
import cPickle as pickle

# FIXME: The core shouldn't depend on a specific toolkit for signalling
import gobject

log = logging.getLogger(__name__)

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

class Mode(gobject.GObject):  # pylint: disable=E1101
    """Data and operations for a timer mode"""
    __gsignals__ = {
        # pylint: disable=E1101
        'notify-tick': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
        'updated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    name = signalled_property('_name', 'updated')
    total = signalled_property('_total', 'updated')
    used = signalled_property('_used', 'updated')
    overflow = signalled_property('_overflow', 'updated')
    show = True

    # pylint: disable=E1002
    def __init__(self, name, total, used=0, overflow=None):
        super(Mode, self).__init__()

        self._name = name
        self._total = total
        self._used = used
        self._overflow = overflow

    def __str__(self):
        return '%s: %s' % (self.name, self.remaining_str())

    def remaining(self):
        """Return the remaining time in this mode as an integer"""
        return self.total - self.used

    def remaining_str(self):
        """Return the remaining time as a pretty-printed string"""
        remaining = round(self.remaining())
        if remaining >= 0:
            return time.strftime('%H:%M:%S', time.gmtime(remaining))
        else:
            return time.strftime('-%H:%M:%S', time.gmtime(abs(remaining)))

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

    def cb_notify_tick(self):
        """Callback used to trigger periodic 'timer expired' notifications."""
        self.emit('notify-tick')  # pylint: disable=E1101

class UnlimitedMode(Mode):
    """Data and operations for modes like Asleep"""
    show = False

    def __str__(self):
        return self.name

    def remaining(self):
        return 1  # TODO: Decide on a better way to do this.

SAFE_MODE_CLASSES = [Mode, UnlimitedMode]
CURRENT_SAVE_VERSION = 6  #: Used for save file versioning
class TimerModel(gobject.GObject):  # pylint: disable=E1101
    """Model class which still needs more refactoring."""
    __gsignals__ = {
        # pylint: disable=E1101
        'action-added': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                         (str, gobject.TYPE_PYOBJECT)),
        'mode-changed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (Mode,)),
        'notify_tick': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (Mode,)),
        'updated': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())
    }

    _selected = None

    # pylint: disable=E1002
    def __init__(self, save_file, defaults=None, start_mode=None):
        super(TimerModel, self).__init__()

        self.last_save = 0
        self.save_file = save_file
        self.default_timers = defaults or {}
        self.start_mode = start_mode
        self.timers = []
        self.actions = []

        self.notify = True
        self._load()
        # IMPORTANT: _load() MUST be called before signals are bound.

        # TODO: Still need to add "Asleep as an explicit mode" migration.
        if not self.selected:
            self.start_mode = (self.get_mode_by_name(start_mode) or
                               self.timers[0])
            self._selected = self.start_mode
        self.active = self._selected

        for mode in self.timers:
            mode.connect('updated', self.cb_updated)
            mode.connect('notify-tick', self.cb_notify_tick)
        self.selected = self.selected
        # FIXME: Why doesn't this cause the button to depress?

    def add_action(self, label, callback):
        self.emit('action-added', label, callback)  # pylint: disable=E1101
        self.actions.append((label, callback))

    def get_mode_by_name(self, name):
        found = [x for x in self.timers if x.name == name]
        if found:
            return found[0]

    # pylint: disable=unused-argument
    def cb_updated(self, mode):
        """Callback used to propagate mode update events upward."""
        self.emit('updated')  # pylint: disable=E1101

    def cb_notify_tick(self, mode):
        """Callback used to propagate notification triggers upwards."""
        self.emit('notify-tick', mode)  # pylint: disable=E1101

    def reset(self):
        """Reset all timers to starting values"""
        for mode in self.timers:
            mode.reset()
        self.selected = self.start_mode

    def _load(self):
        """Load the save file if present. Log and start clean otherwise."""
        if os.path.isfile(self.save_file):
            try:
                # Load the data, but leave the internal state unchanged in case
                # of corruption.

                with open(self.save_file, 'rb') as fobj:
                    loaded = pickle.load(fobj)

                # TODO: Move all the migration code to a different module.
                # TODO: Redesign this based on schema migration design patterns
                #       for maintainability.
                # TODO: Use old Timeclock versions to generate unit test data

                version = loaded[0]

                win_state = {}
                selected_mode = None  # Fallback value
                if version == CURRENT_SAVE_VERSION:
                    version, data = loaded
                    timers = data.get('timers', [])
                    notify = data.get('window', {}).get('enable', True)
                    win_state = data.get('window', {})
                    selected_mode = data.get('selected_mode', None)
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
                elif version == 2:
                    version, total, used = loaded
                    notify = True
                elif version == 1:
                    version, total_old, used_old = loaded
                    translate = ["N/A", "btn_overheadMode", "btn_workMode",
                                 "btn_playMode"]
                    total = dict((translate.index(key), value)
                                 for key, value in total_old.items())
                    used = dict((translate.index(key), value)
                                for key, value in used_old.items())
                    notify = True
                else:
                    raise ValueError(
                        "Save file too new! (Expected %s, got %s)" %
                        (CURRENT_SAVE_VERSION, version))

                if version <= 4:
                    # Out-of-band data from the save files
                    mode_names = ('Asleep', 'Overhead', 'Work', 'Leisure')

                    timers = []
                    for pos, row in enumerate(zip(total, used)):
                        timers.append({
                            'name': mode_names[pos],
                            'total': row[0],
                            'used': row[1],
                        })

                # Sanity checking could go here.

            except Exception, err:  # pylint: disable=broad-except
                log.error("Unable to load save file. Ignoring: %s", err)
                timers = copy.deepcopy(self.default_timers)
            else:
                log.info("Save file loaded successfully")
                # File loaded successfully, now we put the data in place.
                self.notify = notify
                # self.app.saved_state = win_state
                # FIXME: Replace this with some kind of 'loaded' signal.

        else:
            timers = copy.deepcopy(self.default_timers)

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
        if selected_mode:
            selected_mode = self.get_mode_by_name(selected_mode)
            if selected_mode:
                self.selected = selected_mode
        # TODO: I need a way to trigger a rebuild of the view's signal bindings

    # TODO: Reimplement using signalled_property and a signal connect.
    def _get_selected(self):
        """Getter backend for the C{selected} property"""
        return self._selected

    def _set_selected(self, mode):
        """Setter backend for the C{selected} property"""
        target = mode
        if isinstance(mode, basestring):
            target = self.get_mode_by_name(mode)
        if not target:
            log.error("Attempted to set unknown mode: %s", mode)

        self._selected = target
        self.active = self._selected
        # TODO: Figure out what class should bear responsibility for
        # automatically changing self.active when self.mode is changed.
        self.save()
        self.emit('mode-changed', self._selected)  # pylint: disable=E1101

    selected = property(_get_selected, _set_selected)  # pylint: disable=W1001

    def save(self):
        """Exit/Timeout handler for the app. Gets called every five minutes and
        on every type of clean exit except xkill. (PyGTK doesn't let you)

        Saves the current timer values to disk."""
        # TODO: Re-imeplement this properly.
        # window_state = {
        #          'position': self.app.win.get_position(),
        #         'decorated': self.app.win.get_decorated()
        # }
        window_state = {}
        timers = [mode.save() for mode in self.timers]

        data = {
            'timers': timers,
            'notify': {'enable': self.notify},
            'window': window_state,
            'selected_mode': self.selected.name,
        }

        with open(self.save_file + '.tmp', "wb") as fobj:
            pickle.dump((CURRENT_SAVE_VERSION, data), fobj)

        # Windows doesn't let you os.rename to overwrite.
        # TODO: Find another way to atomically replace the state file.
        # TODO: Decide what to do when self.save_file is a directory
        if os.name == 'nt' and os.path.exists(self.save_file):
            os.unlink(self.save_file)

        # Corruption from saving without atomic replace has been observed
        os.rename(self.save_file + '.tmp', self.save_file)
        self.last_save = time.time()
        return True
