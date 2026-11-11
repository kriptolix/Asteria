from gi.repository import Gtk
from gi.repository import Gio, GLib

import logging

from dataclasses import asdict
from pathlib import Path
from collections.abc import Callable
import yaml

from .projecsettings import ProjectSettings


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


def ask_to_save(settings: ProjectSettings,
                parent: Gtk.Window,
                callback, app=None) -> None:

    def _dialog_response(dialog, response):
        result = dialog.choose_finish(response)

        match result:
            case 1:
                settings.save()
                callback(parent)
            case 2:
                callback(parent)
                
    ###

    dialog = Gtk.AlertDialog()
    dialog.set_message("Caution")
    dialog.set_detail("Do you want to save before performing this action?")
    dialog.set_modal(True)
    dialog.set_buttons(["Cancel", "Do Not Save", "Save"])

    dialog.choose(parent, None, _dialog_response)


def load_from_path(settings: ProjectSettings, path: str) -> None:

    def on_loader_finished(loader, result, user_data=None):
        try:
            loader.load_finish(result)
            print(f"File loaded from {path}")
        except Exception as e:
            print(f"Error loading: {e}")
    ###

    file = Gio.File.new_for_path(path)
    loader = GtkSource.FileLoader.new(buffer, file)
    loader.load_async(None, on_loader_finished, None)


def load_by_dialog(settings: ProjectSettings, parent: Gtk.Window) -> None:

    def on_file_chosen(dialog, result, user_data=None):
        try:
            gfile = dialog.open_finish(result)
            sfile = GtkSource.File.new()
            sfile.set_location(gfile)
            loader = GtkSource.FileLoader.new(buffer, sfile)
            loader.load_async(1, None, None, None, None,
                              lambda l, r, u: l.load_finish(r), None)
            print(f"File loaded from {gfile.get_path()}")
        except Exception as e:
            print(f"Error loading via dialog: {e}")
    ###

    if settings.modified:
        ask_to_save(settings, parent, load_by_dialog)
        return

    dialog = Gtk.FileDialog()
    dialog.open(parent, None, on_file_chosen)