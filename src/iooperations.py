from gi.repository import Gtk

import logging

from dataclasses import asdict
from pathlib import Path

import yaml
# from dacite import from_dict
from gi.repository import Gio, GLib

from .configmodel import Config

def choose_directory(parent: Gtk.Window, entry: Gtk.Entry) -> None:

    def _on_folder_selected(dialog, result, user_data=None):
        try:
            folder = dialog.select_folder_finish(result)                        
            entry.set_text(folder.get_path())
          
        except Exception as e:
            logging.error(f"Error loading by dialog: {e}")
    ###   

    dialog = Gtk.FileDialog()
    dialog.select_folder(
        parent,
        None,
        _on_folder_selected,
    )


def ensure_parent(file: Gio.File) -> None:
    parent = file.get_parent()

    if parent is not None:
        parent.make_directory_with_parents()
        

def load_config(path: str | Path) -> Config:
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



