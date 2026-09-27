from gi.repository import Gtk, Gio, GLib

import logging
from datetime import datetime
from typing import Callable

from.serialization import serialize_content, deserialize_content

def set_file_monitor(file: Gio.File) -> None:

    def _on_file_changed(file_monitor: Gio.FileMonitor,
                         file: Gio.File,
                         other_file: Gio.File | None,
                         event_type: Gio.FileMonitorEvent):

        if (event_type == Gio.FileMonitorEvent.Changed):
            print("file was changed, please reload")

        else:
            print("test")

    ##

    file_monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, None)
    file_monitor.connect("changed", _on_file_changed)

def ask_to_save(buffer: Gtk.TextBuffer,
                parent: Gtk.Window,
                callback: Callable, 
                app=None) -> None:

    def _dialog_response(dialog, response):
        result = dialog.choose_finish(response)

        match result:
            case 1:
                buffer.set_modified(False)
                if app:
                    callback(buffer, parent, app)
                    return
                callback(buffer, parent)
            case 2:
                save_by_dialog(buffer, parent, callback)
    ###

    dialog = Gtk.AlertDialog()
    dialog.set_message("Caution")
    dialog.set_detail("Do you want to save before performing this action?")
    dialog.set_modal(True)
    dialog.set_buttons(["Cancel", "Do Not Save", "Save"])

    dialog.choose(parent, None, _dialog_response)

def new_project(buffer: Gtk.TextBuffer, parent: Gtk.Window) -> None:

    if buffer.get_modified():
        ask_to_save(buffer, parent, new_project)
        return

    buffer.set_text("")
    buffer.set_modified(False)

def save_to_file(content: str, file: Gio.File) -> None:

    def _finish_replace(file, result, data):

        try:
            result, tag = file.replace_contents_finish(result)

        except GLib.GError as error:
            logging.error(str(error.message))
            return

        info = file.query_info("standard::display-name",
                                Gio.FileQueryInfoFlags.NONE)

        if info:
            display_name = info.get_attribute_string(
                "standard::display-name")
        else:
            display_name = file.get_basename()

        if not (result):
            logging.error(f"Unable to save {display_name}")

        
    ##    

    byte_content = GLib.Bytes.new(content.encode('utf-8'))

    file.replace_contents_bytes_async(byte_content,
                                       None,
                                       False,
                                       Gio.FileCreateFlags.NONE,
                                       None,
                                       _finish_replace,
                                       None)

def save_to_tmp(buffer, file, 
                project_name, in_progress_content) -> Gio.File:
    
    content = serialize_content(buffer)
    
    if (in_progress_content == content):
        logging.info("No modifiations to save")    
        return

    in_progress_content = content

    if not file:
           
        title = "project-" + project_name
        name = title + datetime.now().strftime("-%Y%m%d%H%M%S")

        path = GLib.get_user_cache_dir() + "/" + name
        file = Gio.File.new_for_path(path)
        
    save_to_file(content)

    buffer.set_modified(False)

    return file

def save_by_dialog(buffer: Gtk.TextBuffer,
                   parent: Gtk.Window, callback=None) -> None:

    def on_file_chosen(dialog, result):
        
        file = dialog.save_finish(result)
        
        content = serialize_content(buffer)

        save_to_file(content, file)

        buffer.set_modified(False)

        if callback:
            callback(buffer, parent)

        
    ###

    dialog = Gtk.FileDialog()
    dialog.save(parent, None, on_file_chosen)

def load_from_file(buffer: Gtk.TextBuffer, file: Gio.File) -> None:

    def _finish_load(file: Gio.File,
                     result: Gio.AsyncResult):
        
        result, byte_content, tag = file.load_contents_finish(result)        

        if not result:
            path = file.peek_path()
            logging.error(f"Unable to open {path}: {byte_content}")
            return

        try:
            content = byte_content.decode('utf-8')
            deserialize_content(buffer, content)

        except UnicodeError as err:
            path = file.peek_path()
            logging.error(
                f"Unable to load the contents of {path}:"
                "the file is not encoded with UTF-8")
            return        

    ##

    file.load_contents_async(None, _finish_load)

def load_by_dialog(buffer: Gtk.TextBuffer, parent: Gtk.Window) -> None:

    def on_file_chosen(dialog, result, user_data=None):
        try:
            file = dialog.open_finish(result)
            
            load_from_file(buffer, file)
          
        except Exception as e:
            logging.error(f"Error loading by dialog: {e}")
    ###

    if buffer.get_modified():
        ask_to_save(buffer, parent, load_by_dialog)
        return

    dialog = Gtk.FileDialog()
    dialog.open(parent, None, on_file_chosen)

def scan_for_tmp():

    recovered_list = []
    tmp_path = GLib.get_user_cache_dir()
    tmp_dir = Gio.File.new_for_path(tmp_path)

    enumerator = tmp_dir.enumerate_children(Gio.FILE_ATTRIBUTE_STANDARD_NAME,
                                            Gio.FileQueryInfoFlags.NONE)
    for info in enumerator:
        file_name = info.get_name()

        if file_name.startswith("project"):

            path = tmp_path + "/" + file_name

            file = Gio.File.new_for_path(path)
            recovered_list.append(file)
    
    return recovered_list

def remove_file(file: Gio.File):

    result = file.delete(None)

    logging.info(result)

def quit(buffer: Gtk.TextBuffer, parent: Gtk.Window, app) -> None:

    if buffer.get_modified():
        ask_to_save(buffer, parent, quit, app)
        return

    app.quit()
