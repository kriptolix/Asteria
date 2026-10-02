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
from gi.repository import Gtk, GObject, Gio

class DataObject(GObject.GObject):

    __gtype_name__ = 'DataObject'

    text = GObject.Property(type=str, default=None)
    image = GObject.Property(type=str, default=None)
    directory = GObject.Property(type=str, default=None)

    def __init__(self, text, image):

        super().__init__()

        self.text = text
        self.image = image        

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/SiteThumb.ui')
class SiteThumb(Gtk.Box):
    __gtype_name__ = 'SiteThumb'
    
    _text = Gtk.Template.Child()
    _thumb = Gtk.Template.Child()
    
    _trash_button = Gtk.Template.Child()
    

    def __init__(self):
        super().__init__()


    def set_trash_icon(self):

        self._motion = Gtk.EventControllerMotion.new()
        self._motion.connect("enter", self._on_mouse_move)
        self._motion.connect("leave", self._on_mouse_move)
        self.add_controller(self._motion)
      
    def set_image(self, image):            
        
        self._thumb.set_filename(image)

    def _on_mouse_move(self, motion, x=None, y=None):        
      
        if x and y:
            self._trash_button.set_visible(True)
            self._trash_button.set_sensitive(True)
            return

        self._trash_button.set_visible(False)
        self._trash_button.set_sensitive(False)

    
        





    