"""UI-related utility functions which may also be used by controllers."""


import os
import cairo, gobject, gtk, pango
import gtk.gdk  # pylint: disable=import-error

__author__ = "Stephan Sokolow (deitarion/SSokolow)"
__license__ = "GNU GPU 2.0 or later"

# Known generated icon sizes.
# TODO: Rewrite this to use Gtk's IconTheme support if present.
# (What DOES happen on Windows with that?)
ICON_SIZES = [16, 22, 32, 48, 64]
SELF_DIR = os.path.dirname(os.path.realpath(__file__))

def get_icon_path(size):
    """Return the path to the largest Timeclock icon which fits in ``size``."""
    for icon_size in sorted(ICON_SIZES, reverse=True):
        if icon_size <= size:
            size = icon_size
            break

    return os.path.join(SELF_DIR, '..', "icons",
            "timeclock_%dx%d.png" % (size, size))

class RoundedWindow(gtk.Window):
    """Undecorated gtk.Window with rounded corners."""
    def __init__(self, corner_radius=10, *args, **kwargs):
        gtk.Window.__init__(self, *args, **kwargs)

        self.corner_radius = corner_radius
        self.connect('size-allocate', self.__cb_size_allocate)
        self.set_decorated(False)

    # pylint: disable=invalid-name,too-many-arguments,no-self-use
    def rounded_rectangle(self, cr, x, y, w, h, r=20):
        """Draw a rounded rectangle using Cairo.
        Source: http://stackoverflow.com/q/2384374/435253

        This is just one of the samples from
        http://www.cairographics.org/cookbook/roundedrectangles/
          A****BQ
         H      C
         *      *
         G      D
          F****E
        """

        cr.move_to(x + r, y)                           # Move to A
        cr.line_to(x + w - r, y)                       # Straight line to B
        cr.curve_to(x + w, y, x + w, y, x + w, y + r)  # Crv to C, Ctrl pts @ Q
        cr.line_to(x + w, y + h - r)                   # Move to D
        cr.curve_to(x + w, y + h, x + w, y + h, x + w - r, y + h)  # Curve to E
        cr.line_to(x + r, y + h)                       # Line to F
        cr.curve_to(x, y + h, x, y + h, x, y + h - r)  # Curve to G
        cr.line_to(x, y + r)                           # Line to H
        cr.curve_to(x, y, x, y, x + r, y)              # Curve to A

    def __cb_size_allocate(self, win, allocation):
        """Callback to round the window whenever its size is set."""
        w, h = allocation.width, allocation.height
        bitmap = gtk.gdk.Pixmap(None, w, h, 1)
        cr = bitmap.cairo_create()

        # Clear the bitmap
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()

        # Draw our shape into the bitmap using cairo
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        self.rounded_rectangle(cr, 0, 0, w, h, self.corner_radius)
        cr.fill()

        # Set the window shape
        win.shape_combine_mask(bitmap, 0, 0)

class OSDWindow(RoundedWindow):
    """Simple OSD overlay for notifications"""

    font = pango.FontDescription("Sans Serif 22")

    def __init__(self, corner_radius=25, monitor=None, font=None,
                 *args, **kwargs):
        super(OSDWindow, self).__init__(type=gtk.WINDOW_POPUP,
                corner_radius=corner_radius, *args, **kwargs)

        self.font = font or self.font
        self.timeout_id = None
        self._add_widgets()
        self.monitor_geom = monitor or None

        if self.monitor_geom:
            self.connect_after("size-allocate", self.__cb_size_allocate)
        else:
            self.set_position(gtk.WIN_POS_CENTER_ALWAYS)

    def _add_widgets(self):
        """Override to change a subclass's contents"""
        # pylint: disable=attribute-defined-outside-init
        self.label = gtk.Label()
        self.label.modify_font(self.font)
        self.add(self.label)

        self.set_border_width(10)

    def _set_message(self, msg):
        """Override when overriding _add_widgets"""
        self.label.set_text(msg)

    def __cb_size_allocate(self, widget, allocation):
        """Callback to re-center the window as its contents change"""
        if widget.monitor_geom and widget.window:
            geom = widget.monitor_geom

            # We need this to prevent a race which breaks move()
            while gtk.events_pending():
                gtk.main_iteration_do(False)

            widget.window.move(
                geom.x + (geom.width / 2) - (allocation.width / 2),
                geom.y + (geom.height / 2) - (allocation.height / 2))
        return False

    def cb_timeout(self):
        """Callback for when the OSD times out"""
        self.timeout_id = None
        self.hide()
        return False

    def hide(self):
        """Manually hide the OSD if visible"""
        if self.timeout_id:
            gobject.source_remove(self.timeout_id)
        super(OSDWindow, self).hide()

    def message(self, text, timeout):
        """Display the window with a specified message and timeout.

        If the timeout is <= 0, the OSD will remain until manually dismissed.
        """
        self.show_all()
        self._set_message(text)

        if self.timeout_id:
            gobject.source_remove(self.timeout_id)
        if timeout > 0:
            self.timeout_id = gobject.timeout_add_seconds(
                                int(timeout), self.cb_timeout)

class MultiMonitorOSD(gobject.GObject):
    """An OSD manager which handles multiple monitors.

    @todo: Probably time to move OSD handling into its own module.
    """
    def __init__(self, model, font=None):
        super(MultiMonitorOSD, self).__init__()

        self.font = font or OSDWindow.font
        self.windows = {}

        display_manager = gtk.gdk.display_manager_get()
        for display in display_manager.list_displays():
            self.cb_display_opened(display_manager, display)

        #model.connect('tick', self.cb_cycle_osd)
        display_manager.connect("display-opened", self.cb_display_opened)

    def cb_display_closed(self, display, is_error):
        """@todo: Handler to clean up after a display is closed."""
        pass  # TODO: Dereference and destroy the corresponding OSDWindows.

    def cb_display_opened(self, manager, display):
        """Handler to start listening when a new display is opened."""
        for screen_num in range(0, display.get_n_screens()):
            screen = display.get_screen(screen_num)

            self.cb_monitors_changed(screen)
            screen.connect("monitors-changed", self.cb_monitors_changed)

        display.connect('closed', self.cb_display_closed)

    def cb_monitors_changed(self, screen):
        """Handler to adapt to changing desktop geometry"""
        #FIXME: This must handle changes and deletes in addition to adds.
        for monitor_num in range(0, screen.get_n_monitors()):
            display_name = screen.get_display().get_name()
            screen_num = screen.get_number()
            geom = screen.get_monitor_geometry(monitor_num)

            key = (display_name, screen_num, tuple(geom))
            if key not in self.windows:
                window = OSDWindow(font=self.font, monitor=geom)
                window.set_screen(screen)
                self.windows[key] = window

    def hide(self):
        """Hide all OSD windows."""
        for win in self.windows.values():
            win.hide()

    def message(self, msg, timeout):
        """Display an OSD on each monitor"""
        for win in self.windows.values():
            win.message(msg, timeout)
