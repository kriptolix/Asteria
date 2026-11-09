# main.py
#
# Copyright 2026 k
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

from gettext import gettext as _
from pathlib import Path

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Gio, Adw
from src.gtk.widgets.mainwindow import MainWindow
from src.gtk.widgets.dialogcreate import DialogCreate
from .projecsettings import ProjectSettings

from .iooperations import choose_directory

class AsteriaApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='io.github.Kriptolix.Asteria',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/io/github/Kriptolix/Asteria')
        self.create_action('quit', lambda *_: self.quit(), ['<control>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)

        self.project_dir = None
        self.project_config = None

        # print(self.project_dir.exists())
        # print(self.project_dir.is_dir())
        # print(self.project_dir.is_file())        

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        self.window = self.props.active_window
        if not self.window:
            self.window = MainWindow(app=self)
        self.window.present()

        self.window._navigation_view

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutDialog(application_name='Asteria',
                                application_icon='io.github.Kriptolix.Asteria',
                                developer_name='k',
                                version='0.1.0',
                                # Translators: Replace "translator-credits" with your name/username, and optionally an email or URL.
                                translator_credits = _('translator-credits'),
                                developers=['k'],
                                copyright='© 2026 k')
        about.present(self.props.active_window)

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        print('app.preferences action activated')

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)

    def setup_project(self):

        def _create_project(items):
            project_name = items[0]
            project_gdir = items[1]
            project_path = Path(project_gdir.get_path()) / project_name

            create_new_project(project_path) #the lib use Path to be S.O. agnostic
            self.project_dir = project_gdir.get_child(project_name)
            # self.project_dir = parent_dir.get_child("sitedev")
            self.load_config()
            
        dialog = DialogCreate(self.window, _create_project)
        dialog.present(self.window)

    def load_config(self):

        project_path = Path(self.project_dir.get_path())
        self.project_config = ProjectSettings.load(project_path)

        self.window._projectpage._sidebar.set_config()
        
        self.window.go_to_project_page(None, None)
        self.window._projectpage.create_server()  

    def open_project(self):
        def _on_chosen(gdir):
            self.project_dir = gdir
            self.load_config()

        choose_directory(self.window, _on_chosen)


    def update_project(self, button):
        self.window._projectpage._sidebar.get_config()
        self.project_config.save()
        


def main(version):
    """The application's entry point."""
    app = AsteriaApplication()
    return app.run(sys.argv)
