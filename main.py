import enum
import os
import gi
import subprocess
from typing import cast

from hyprland import current_clients, ClassStructure, ICON_SIZE

gi.require_version("Gtk", "3.0")
gi.require_version("Rsvg", "2.0")

from gi.repository import GLib, Gtk
from fabric import Application, Service, Signal, Property
from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.svg import Svg as FabricSvg

CSS_STYLES = """
window { background-color: transparent; }
#icon-bar-box {
   background-color: rgba(30, 30, 46, 0.9);
   border-radius: 12px;
   padding: 8px;
   border: 1px solid rgba(137, 180, 250, 0.8);
   min-height: 52px;
}

/* Solo estilizamos el botón para que sea invisible */
.icon-button {
    background: none;
    border: none;
    padding: 0;
}
"""

BAR_WIDTH = 100
BAR_HEIGHT = 104
HOVER_SCALE = 1.4
ANIMATION_DURATION = 0.5


class Animator(Service):
    @Signal
    def finished(self) -> None: ...

    @Property(tuple[float, float, float, float], "read-write")
    def bezier_curve(self) -> tuple[float, float, float, float]:
        return self._bezier_curve

    @bezier_curve.setter
    def bezier_curve(self, value: tuple[float, float, float, float]):
        self._bezier_curve = value

    @Property(float, "read-write")
    def value(self):
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value

    @Property(float, "read-write")
    def max_value(self):
        return self._max_value

    @max_value.setter
    def max_value(self, value: float):
        self._max_value = value

    @Property(float, "read-write")
    def min_value(self):
        return self._min_value

    @min_value.setter
    def min_value(self, value: float):
        self._min_value = value

    @Property(bool, "read-write", default_value=False)
    def playing(self):
        return self._playing

    @playing.setter
    def playing(self, value: bool):
        self._playing = value

    @Property(bool, "read-write", default_value=False)
    def repeat(self):
        return self._repeat

    @repeat.setter
    def repeat(self, value: bool):
        self._repeat = value

    def __init__(
        self,
        bezier_curve: tuple[float, float, float, float],
        duration: float,
        min_value: float = 0.0,
        max_value: float = 1.0,
        repeat: bool = False,
        tick_widget: Gtk.Widget | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._bezier_curve = (1, 0, 1, 1)
        self.duration = duration
        self._value = 0.0
        self._min_value = 0.0
        self._max_value = 1.0
        self._repeat = False
        self.bezier_curve = bezier_curve
        self.value = min_value
        self.min_value = min_value
        self.max_value = max_value
        self.repeat = repeat
        self.playing = False
        self._start_time = None
        self._tick_handler = None
        self._timeline_pos = 0
        self._tick_widget = tick_widget

    def do_get_time_now(self):
        return GLib.get_monotonic_time() / 1_000_000

    def do_lerp(self, start: float, end: float, time: float) -> float:
        return start + (end - start) * time

    def do_interpolate_cubic_bezier(self, time: float) -> float:
        y_points = (0, self.bezier_curve[1], self.bezier_curve[3], 1)
        return (
            (1 - time) ** 3 * y_points[0]
            + 3 * (1 - time) ** 2 * time * y_points[1]
            + 3 * (1 - time) * time**2 * y_points[2]
            + time**3 * y_points[3]
        )

    def do_ease(self, time: float) -> float:
        return self.do_lerp(
            self.min_value, self.max_value, self.do_interpolate_cubic_bezier(time)
        )

    def do_update_value(self, delta_time: float):
        if not self.playing:
            return
        elapsed_time = delta_time - cast(float, self._start_time)
        self._timeline_pos = min(1, elapsed_time / self.duration)
        self.value = self.do_ease(self._timeline_pos)
        if not self._timeline_pos >= 1:
            return
        if not self.repeat:
            self.value = self.max_value
            self.finished()
            self.pause()
            return
        self._start_time = delta_time
        self._timeline_pos = 0

    def do_handle_tick(self, *_):
        current_time = self.do_get_time_now()
        self.do_update_value(current_time)
        return True

    def do_remove_tick_handlers(self):
        if self._tick_handler:
            if self._tick_widget:
                self._tick_widget.remove_tick_callback(self._tick_handler)
            else:
                GLib.source_remove(self._tick_handler)
        self._tick_handler = None

    def play(self):
        if self.playing:
            return
        self._start_time = self.do_get_time_now()
        if not self._tick_handler:
            if self._tick_widget:
                self._tick_handler = self._tick_widget.add_tick_callback(
                    self.do_handle_tick
                )
            else:
                self._tick_handler = GLib.timeout_add(16, self.do_handle_tick)
        self.playing = True

    def pause(self):
        self.playing = False
        self.do_remove_tick_handlers()

    def stop(self):
        self.pause()
        self._timeline_pos = 0


class AnimatedIconButton(Gtk.Button):
    def __init__(self, svg_file: str, base_size: int, **kwargs):
        super().__init__(**kwargs)
        self.get_style_context().add_class("icon-button")

        self.icon_widget = FabricSvg(svg_file=svg_file, size=base_size)
        self.add(self.icon_widget)

        hover_size = int(base_size * HOVER_SCALE)

        self.grow_animator = Animator(
            bezier_curve=(0.34, 1.56, 0.64, 1.0),
            duration=ANIMATION_DURATION,
            min_value=base_size,
            max_value=hover_size,
            tick_widget=self,
        )
        self.shrink_animator = Animator(
            bezier_curve=(0.34, 1.56, 0.64, 1.0),
            duration=ANIMATION_DURATION,
            min_value=hover_size,
            max_value=base_size,
            tick_widget=self,
        )

        self.grow_animator.connect("notify::value", self._on_animation_tick)
        self.shrink_animator.connect("notify::value", self._on_animation_tick)

        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)

    def _on_animation_tick(self, animator, _):
        new_size = int(animator.value)
        self.icon_widget.set_size_request(new_size, new_size)

    def _on_enter(self, _, __):
        self.shrink_animator.stop()
        self.grow_animator.min_value = self.icon_widget.get_allocated_width()
        self.grow_animator.play()

    def _on_leave(self, _, __):
        self.grow_animator.stop()
        self.shrink_animator.min_value = self.icon_widget.get_allocated_width()
        self.shrink_animator.play()


class IconBar(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(
            layer="top", anchor="bottom center", exclusivity="ignore", **kwargs
        )
        self.set_size_request(BAR_WIDTH, BAR_HEIGHT)
        self.icon_box = Box(
            name="icon-bar-box",
            orientation="horizontal",
            spacing=10,
            halign="center",
            valign="center",
        )
        self.add(self.icon_box)
        self.hide()
        GLib.idle_add(self.populate_bar)

    def populate_bar(self):
        active_apps = current_clients()

        for wm_class, data in active_apps.items():
            icon_path = data[ClassStructure.ICON_PATH.value]
            print(f"Procesando: Clase='{wm_class}', Icono='{icon_path}'")

            if not icon_path or not os.path.exists(icon_path):
                print(f"Omitido: {wm_class}")
                continue
            try:
                button = AnimatedIconButton(svg_file=icon_path, base_size=ICON_SIZE)

                command = f"hyprctl dispatch focuswindow class:^{wm_class}$"
                button.connect(
                    "clicked", lambda _, cmd=command: subprocess.run(cmd, shell=True)
                )

                self.icon_box.add(button)
                print(f"OK: Icono '{wm_class}' añadido.")
            except Exception as e:
                print(f"  -> ERROR: No se pudo cargar '{icon_path}'. Razón: {e}")

        self.show_all()
        return GLib.SOURCE_REMOVE


if __name__ == "__main__":
    app = Application("hyprland-icon-bar")
    bar = IconBar()
    app.add_window(bar)
    app.set_stylesheet_from_string(CSS_STYLES)
    app.run()
