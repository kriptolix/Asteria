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

from gi.repository import Gtk, Gio, Adw, GLib
from src.gtk.widgets.mainwindow import MainWindow
from src.gtk.widgets.dialogcreate import DialogCreate
from .projecsettings import ProjectSettings
from .asteria.api import create_new_project

from .iooperations import choose_directory
from .util import create_action

class AsteriaApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(application_id='io.github.Kriptolix.Asteria',
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
                         resource_base_path='/io/github/Kriptolix/Asteria')
        
        create_action(self, "app", "quit", self._on_actions,
                      ['<primary>q'])
        create_action(self, "app", 'new',
                      self._on_actions, ['<Ctrl>n'])
        create_action(self, "app", 'open',
                      self._on_actions, ['<Ctrl>o'])
        create_action(self, "app", 'about', self._on_about_action, None, None)

        self.project_dir = None
        self.project_config = None              

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        self.window = self.props.active_window
        if not self.window:
            self.window = MainWindow(app=self)
        self.window.present()
       

    def new_project(self):

        def _create_project(items):
            project_name = items[0]
            project_gdir = items[1]
            project_path = Path(project_gdir.get_path()) / project_name

            create_new_project(project_path) #the lib use Path to be S.O. agnostic
            self.project_dir = project_gdir.get_child(project_name)
            
            self.load_config()
            
        dialog = DialogCreate(self.window, _create_project)
        dialog.present(self.window)

    def load_config(self):

        project_path = Path(self.project_dir.get_path())
        self.project_config = ProjectSettings.load(project_path)

        self.window._sidebar.set_config() 
        self.window._content.create_server() 
        self.window._content.create_webview() 

    def open_project(self):
        def _on_chosen(gdir):
            self.project_dir = gdir
            self.load_config()

        choose_directory(self.window, _on_chosen)


    def update_project(self, button):
        self.window._sidebar.get_config()
        self.project_config.save()
        self.window._content.site_rebuild()


    def _on_quit_button(self, window):
    
            self.activate_action("quit",
                                 GLib.Variant.new_boolean(True))
            return True
            
    
    def _on_shortcuts(self, *args):

        builder = Gtk.Builder.new_from_resource(
            '/io/github/kriptolix/Asteria/src/gtk/ui/Shortcuts.ui'
        )

        shortcuts = builder.get_object("shortcuts")
        shortcuts.set_transient_for(self.window)
        shortcuts.present()


    def _on_about_action(self, *args):

        about = Adw.AboutDialog.new_from_appdata(
            '/io/github/kriptolix/Asteria'
            '/data/io.github.Kriptolix.Asteria.metainfo.xml.in',
            '0.8.0'
        )

        about.set_translator_credits(_('translator-credits'))
        about.present(self.props.active_window)


    def _on_actions(self, action: Gio.SimpleAction, parameter):               

        action_name = action.get_name()

        match action_name:
            case "open":
                self.open_project()
            case "new":
                self.new_project()            
            case "quit":
                quit()
        


def main(version):
    """The application's entry point."""
    app = AsteriaApplication()
    return app.run(sys.argv)
