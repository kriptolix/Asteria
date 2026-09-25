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
from gi.repository import Gtk, Gio, GObject

from src.gtk.widgets.sitethumb import SiteThumb, DataObject

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/StartPage.ui')
class StartPage(Adw.NavigationPage):
    __gtype_name__ = 'StartPage'

    _presentation = Gtk.Template.Child()
    _grid_view = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

        
        self.factory = Gtk.SignalListItemFactory()
        self.factory.connect("setup", self._on_setup)
        self.factory.connect("bind", self._on_bind)
        self._grid_view.set_factory(self.factory)

        store = Gio.ListStore.new(DataObject)

        selection = Gtk.NoSelection()

        selection.set_model(store)

        self._grid_view.set_model(selection)

        v1 = DataObject("entrada 01")
        v2 = DataObject("entrada 02")
        store.append(v1)
        store.append(v2)


    def _on_setup(self,
                  factory: Gtk.SignalListItemFactory,
                  item: Gtk.ListItem) -> None:
        """Setup the widget to show in the Gtk.Listview"""

        widget = SiteThumb()   
        item.set_child(widget)

    def _on_bind(self,
                 factory: Gtk.SignalListItemFactory,
                 item: Gtk.ListItem) -> None:
        """bind data from the NodeObject to the visible widget"""

        
        node_widget = item.get_child()
        node_object = item.get_item()

        node_widget._text.props.label = node_object.text        

        node_widget._text.bind_property("label", node_object, "text", flags=GObject.BindingFlags.SYNC_CREATE)