from gi.repository import Gtk, Gio, GLib

import threading
from typing import Callable


def create_action(action_group: Gio.SimpleActionGroup, prefix: str,
                  name: str, callback: Callable, shortcuts: list[str] | None,
                  parameter=None, target=None) -> None:
    """
    Add an action to an action group.

    Parameters
    ----------
    action_group : Where the actions is added
    prefix : Prefix used to actions on action group
    name : The name of the action.
    callback : function to be called when the action is activated.
    shortcuts : An optional list of strings representing accelerators.
    parameter : Optional parameters for the action.
    target : Optional standard value to action parameter.
    """

    action = Gio.SimpleAction.new(name, parameter)
    action.connect("activate", callback)
    action_group.add_action(action)
    detailed_name = f"{prefix}.{name}"

    if (target):
        detailed_name = f"{prefix}.{name}::{target}"

    if shortcuts:
        action_group.set_accels_for_action(detailed_name, shortcuts)


def create_click(widget: Gtk.Widget, btn_number: int,
                 trigger: str, callback: Callable, data=None) -> None:
    """
    Add an click action to a widget.

    Parameters
    ----------
    widget : Where the actions is added.
    btn_number : Mouse button number that will activate de action.
    trigger : Button behavior that will triggered the action.
    callback : Function to be called when the action is activated.
    data : Optional Data to pass to callback.
    """

    click = Gtk.GestureClick.new()
    click.set_button(btn_number)
    click.connect(trigger, callback, data)

    widget.add_controller(click)


def update_recent_projects(settings: Gio.Settings, path: str) -> None:

    recent_projects = settings.get_strv("recent-projects")

    if (path in recent_projects):
        recent_projects.remove(path)

    recent_projects.insert(0, path)

    if (len(recent_projects) >= 4):
        recent_projects.pop()

    settings.set_strv("recent-projects", recent_projects)


class Debouncer:

    def __init__(self, seconds, method):
        self.seconds = seconds
        self.method = method
        self._timer = None

    def update_count(self, *args):

        if self._timer is not None:
            self._timer.cancel()

        self._timer = threading.Timer(self.seconds, self.method)
        self._timer.start()


