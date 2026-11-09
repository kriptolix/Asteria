from gi.repository import Gtk
from gi.repository import Gio, GLib

import logging

from dataclasses import asdict
from pathlib import Path
from collections.abc import Callable
import yaml
# from dacite import from_dict

from .util import Directory

def ensure_parent(file: Gio.File) -> None:
    parent = file.get_parent()

    if parent is not None:
        parent.make_directory_with_parents()
        

def choose_directory(parent: Gtk.Window, callback: Callable) -> None:

    def _on_selected(dialog, result):
        try:
            gdir = dialog.select_folder_finish(result)                       
            callback(gdir)
          
        except Exception as e:
            logging.error(f"Error loading by dialog: {e}")
    ###   

    dialog = Gtk.FileDialog()
    dialog.select_folder(
        parent,
        None,
        _on_selected,
    )


def choose_file(parent: Gtk.Window, callback: Callable, directory: Gio.File | None,):

    def on_selected(dialog, result):
        try:
            gfile = dialog.open_finish(result)         
            callback(gfile)

        except Exception as e:
            logging.error(f"Error selecting file: {e}")

    dialog = Gtk.FileDialog()

    if directory:
        dialog.set_initial_folder(directory)

    dialog.open(parent, None, on_selected)


def open_with_app(parent: Gtk.Window, path: Gio.File):

    def _open_launcher(launcher, result):
        try:
            launcher.launch_finish(result)
        except Exception as e:
            print(f"Error opening: {e}")

    ###
    
    launcher = Gtk.FileLauncher.new(path)

    launcher.launch(
        parent,
        None,
        lambda launcher, result: _open_launcher(launcher, result)
    )


def list_subdirectories(gfile: Gio.File) -> Gtk.StringList:
    
    string_list = Gtk.StringList.new([])

    try:
        enumerator = gfile.enumerate_children(
            "standard::name,standard::type",
            Gio.FileQueryInfoFlags.NONE,
            None
        )

        while info := enumerator.next_file(None):
            if info.get_file_type() == Gio.FileType.DIRECTORY:
                string_list.append(info.get_name())

        enumerator.close(None)

    except GLib.Error as e:
        print(f"Error listing directories: {e}")

    return string_list


def list_css_files(gfile: Gio.File) -> Gtk.StringList:
    string_list = Gtk.StringList.new([])

    try:
        enumerator = gfile.enumerate_children(
            "standard::name,standard::type",
            Gio.FileQueryInfoFlags.NONE,
            None
        )

        while info := enumerator.next_file(None):
            if (
                info.get_file_type() == Gio.FileType.REGULAR
                and info.get_name().lower().endswith(".css")
            ):
                string_list.append(info.get_name().rsplit('.', 1)[0])

        enumerator.close(None)

    except GLib.Error as e:
        print(f"Error listing CSS files: {e}")

    return string_list


def create_model(gdir):
    
    model = Gtk.StringList.new([])

  


"""
def load_config(path: str | Path):
    file = Gio.File.new_for_path(str(path))

    if not file.query_exists():
        return Config()

    try:
        success, contents, _etag = file.load_contents()

        if not success:
            return Config()

        data = yaml.safe_load(contents.decode("utf-8")) or {}

        # return from_dict(Config, data)

    except (GLib.Error, UnicodeDecodeError, yaml.YAMLError, ValueError):
        return Config()


def save_config(config: Config, path: str | Path) -> None:
    file = Gio.File.new_for_path(str(path))

    data = yaml.safe_dump(
        asdict(config),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

    contents = data.encode("utf-8")

    file.replace_contents(
        contents,
        None,
        False,
        Gio.FileCreateFlags.REPLACE_DESTINATION,
        None,
    )

"""