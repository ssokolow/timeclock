import os
import cairo, gtk

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
        self.connect('size-allocate', self._on_size_allocate)
        self.set_decorated(False)

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

    def _on_size_allocate(self, win, allocation):
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
