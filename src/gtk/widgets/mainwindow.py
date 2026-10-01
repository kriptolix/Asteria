# window.py
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

from gi.repository import Adw
from gi.repository import Gtk, Gdk

from .startpage import StartPage
from .projectpage import ProjectPage
 

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/MainWindow.ui')
class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MainWindow'

    _navigation_view = Gtk.Template.Child()  

    def __init__(self, app):
        super().__init__(application=app)

        self.application = app

        self._startpage = StartPage()
        self._projectpage = ProjectPage()
        self._navigation_view.add(self._startpage)  

        self._startpage._grid_view.connect("activate", self.change_page)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/io/github/Kriptolix/'
                                        'Asteria/data/asteria.css')
        add_provider = Gtk.StyleContext.add_provider_for_display
        add_provider(Gdk.Display.get_default(),
                     css_provider,
                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        

    def change_page(self, gridview:Gtk.GridView, position:int) -> None:

        if position == 0:
            self.application.setup_project()
            return

        self._navigation_view.push(self._projectpage)        

    def go_back(self, button):
         self._navigation_view.pop()
         self._back_button.set_visible(False)