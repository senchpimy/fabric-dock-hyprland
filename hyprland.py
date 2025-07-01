import time
import enum
import concurrent.futures
import gi
import os
import subprocess

from hyprpy import Hyprland

instance = Hyprland()

ICON_SIZE = 48


class ClassStructure(enum.Enum):
    ICON_PATH = 0
    WINDOWS = 1


# For some reason you can either use this or fabric, not both.
# def find_icon_path(app_id: str, size: int) -> str | None:
#    icon_theme = Gtk.IconTheme.get_default()
#
#    icon_info = icon_theme.lookup_icon(app_id, size, Gtk.IconLookupFlags.FORCE_SIZE)
#
#    if icon_info:
#        return icon_info.get_filename()
#
#    return None


def find_icon_path(app_id: str, size: int) -> str | None:
    icon_dirs = ["/usr/share/icons", os.path.expanduser("~/.local/share/icons")]
    filenames_to_try = [
        f"{app_id}.svg",
        f"{app_id}.png",
        app_id,
    ]

    for dir_path in icon_dirs:
        if not os.path.isdir(dir_path):
            continue
        for filename in filenames_to_try:
            command = ["find", "-L", dir_path, "-iname", filename, "-print", "-quit"]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=1,
                )
                path = result.stdout.strip()
                if path and os.path.exists(path):
                    return path
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
    return None


class Window:
    def __init__(self, title, workspace):
        self.title = title
        self.workspace = workspace

    def __repr__(self):
        return f"Window(title={self.title},  workspace={self.workspace})"


# def current_clients():
#    t = time.time()
#    clases = {}
#    for i in instance.get_windows():
#        obj = Window(i.title, i.workspace)
#        if i.wm_class not in clases:
#            print(f"Añadiendo clase '{i.wm_class}' con título '{i.title}'")
#            icon_path = find_icon_path(i.wm_class, ICON_SIZE)
#            clases[i.wm_class] = (icon_path, [])
#        clases[i.wm_class][ClassStructure.WINDOWS.value].append(obj)
#    print(f"Tiempo de ejecución: {time.time() - t:.2f} segundos")
#    return clases


def current_clients():
    t = time.time()
    clases = {}
    clases_a_buscar = set()

    for i in instance.get_windows():
        obj = Window(i.title, i.workspace)
        wm_class = i.wm_class

        if wm_class not in clases:
            clases[wm_class] = (None, [])
            clases_a_buscar.add(wm_class)

        clases[wm_class][ClassStructure.WINDOWS.value].append(obj)

    resultados_iconos = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_class = {
            executor.submit(find_icon_path, wm_class, ICON_SIZE): wm_class
            for wm_class in clases_a_buscar
        }

        for future in concurrent.futures.as_completed(future_to_class):
            wm_class = future_to_class[future]
            try:
                icon_path = future.result()
                resultados_iconos[wm_class] = icon_path
            except Exception as exc:
                resultados_iconos[wm_class] = None

    for wm_class, icon_path in resultados_iconos.items():
        _, windows_list = clases[wm_class]
        clases[wm_class] = (icon_path, windows_list)

    print("--- Escaneo de clientes completado ---")
    print(f"Tiempo de ejecución: {time.time() - t:.2f} segundos")
    return clases
