import math
import gi
import subprocess

gi.require_version("Gtk", "3.0")
gi.require_version("Rsvg", "2.0")

from gi.repository import GLib, Gtk, Gdk
from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.svg import Svg as FabricSvg

from hyprland import current_clients, ClassStructure, ICON_SIZE

MAX_ICON_SIZE = 96
AFFECT_DISTANCE = 150
ANIMATION_INTERVAL_MS = 15
ANIMATION_STEP = 2

BAR_WIDTH = 200
BAR_HEIGHT = MAX_ICON_SIZE + 26

CSS_STYLES = """
window { background-color: transparent; }
#icon-bar-box {
   background-color: rgba(30, 30, 46, 0.85);
   border-radius: 16px;
   padding: 8px;
   border: 1px solid rgba(137, 180, 250, 0.7);
}
eventbox { background-color: transparent; }
"""


class IconBar(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(
            layer="top", anchor="bottom center", exclusivity="ignore", **kwargs
        )
        self.set_size_request(BAR_WIDTH, BAR_HEIGHT)

        self.is_mouse_over = False
        self.current_max_size = ICON_SIZE
        self.animation_timer_id = None
        self.last_mouse_x = 0

        self.icon_box = Box(
            name="icon-bar-box",
            orientation="horizontal",
            spacing=10,
            halign="center",
            valign="center",
        )
        self.add(self.icon_box)

        self.icons = []
        self.icon_rest_positions = []

        self.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
        )
        self.connect("motion-notify-event", self.on_mouse_move)
        self.connect("leave-notify-event", self.on_mouse_leave)
        self.connect("enter-notify-event", self.on_mouse_enter)

        self.populate_bar()

    def populate_bar(self):
        active_apps = current_clients()
        for wm_class, data in active_apps.items():
            icon_path = data[ClassStructure.ICON_PATH.value]
            if not icon_path:
                continue
            try:
                svg_widget = FabricSvg(svg_file=icon_path, size=ICON_SIZE)
                event_box = Gtk.EventBox()
                event_box.add(svg_widget)
                event_box.connect(
                    "button-press-event", lambda w, e, c=wm_class: self.on_icon_click(c)
                )
                self.icon_box.add(event_box)
                self.icons.append(
                    {"event_box": event_box, "svg": svg_widget, "wm_class": wm_class}
                )
            except Exception as e:
                print(f"ERROR: No se pudo cargar el icono '{icon_path}'. Razón: {e}")
        self.show_all()
        GLib.idle_add(self.cache_icon_positions)

    def cache_icon_positions(self):
        print("INFO: Cacheando posiciones iniciales de los iconos.")
        self.icon_rest_positions.clear()
        for icon_info in self.icons:
            alloc = icon_info["event_box"].get_allocation()
            center_x = alloc.x + (alloc.width / 2)
            self.icon_rest_positions.append(center_x)
        return GLib.SOURCE_REMOVE

    def on_icon_click(self, wm_class: str):
        print(f"Icono de la clase '{wm_class}' ha sido clickeado.")
        command = f"hyprctl dispatch focuswindow class:^{wm_class}$"
        subprocess.run(command, shell=True)
        return True

    def on_mouse_enter(self, widget, event):
        """Cancela cualquier animación de salida y comienza la de entrada."""
        self.is_mouse_over = True
        self.last_mouse_x = event.x

        if self.animation_timer_id is not None:
            GLib.source_remove(self.animation_timer_id)

        print("INFO: Iniciando animación de entrada...")
        self.animation_timer_id = GLib.timeout_add(
            ANIMATION_INTERVAL_MS, self._animate_entry
        )
        return True

    def on_mouse_leave(self, widget, event):
        """Cancela cualquier animación de entrada y comienza la de salida."""
        if event.detail == Gdk.NotifyType.INFERIOR:
            return True

        self.is_mouse_over = False

        if self.animation_timer_id is not None:
            GLib.source_remove(self.animation_timer_id)

        print("INFO: Iniciando animación de salida...")
        self.animation_timer_id = GLib.timeout_add(
            ANIMATION_INTERVAL_MS, self._animate_exit
        )
        return True

    def on_mouse_move(self, widget, event):
        if not self.is_mouse_over:
            return True
        self.last_mouse_x = event.x
        self._update_icon_sizes()
        return True

    def _animate_entry(self):
        """Animación de crecimiento: incrementa el tamaño máximo."""
        if self.current_max_size < MAX_ICON_SIZE:
            self.current_max_size = min(
                self.current_max_size + ANIMATION_STEP, MAX_ICON_SIZE
            )
            self._update_icon_sizes()
            return GLib.SOURCE_CONTINUE
        else:
            self.animation_timer_id = None
            return GLib.SOURCE_REMOVE

    def _animate_exit(self):
        """NUEVA: Animación de contracción: decrementa el tamaño máximo."""
        if self.current_max_size > ICON_SIZE:
            self.current_max_size = max(
                self.current_max_size - ANIMATION_STEP, ICON_SIZE
            )
            self._update_icon_sizes()
            return GLib.SOURCE_CONTINUE
        else:
            self.animation_timer_id = None
            return GLib.SOURCE_REMOVE

    def _update_icon_sizes(self):
        """Calcula y aplica el tamaño a cada icono. No cambia."""
        if not self.icon_rest_positions:
            return

        box_allocation = self.icon_box.get_allocation()
        mouse_x_in_box = self.last_mouse_x - box_allocation.x

        for i, icon_info in enumerate(self.icons):
            icon_center_x = self.icon_rest_positions[i]
            distance = abs(icon_center_x - mouse_x_in_box)

            if distance < AFFECT_DISTANCE:
                scale_factor = (math.cos(distance / AFFECT_DISTANCE * math.pi) + 1) / 2
                size_range = self.current_max_size - ICON_SIZE
                new_size = ICON_SIZE + (size_range * scale_factor)
            else:
                new_size = ICON_SIZE

            icon_info["svg"].set_size_request(int(new_size), int(new_size))


if __name__ == "__main__":
    app = Application("hyprland-icon-bar")
    bar = IconBar()
    app.add_window(bar)
    app.set_stylesheet_from_string(CSS_STYLES)
    app.run()
