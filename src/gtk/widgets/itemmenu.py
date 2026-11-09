from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ItemMenu.ui')
class ItemMenu(Adw.ActionRow):
    __gtype_name__ = 'ItemMenu'

    _remove_button = Gtk.Template.Child()
    _grab_image = Gtk.Template.Child()    

    def __init__(self, title):
            super().__init__()

            self.set_title(title)            

            self._motion = Gtk.EventControllerMotion.new()
            self._motion.connect("enter", self._on_mouse_move)
            self._motion.connect("leave", self._on_mouse_move)
            self.add_controller(self._motion)

    def _on_mouse_move(self, motion, x=None, y=None):            
            
            if x and y:
                self._remove_button.set_visible(True)
                self._remove_button.set_sensitive(True)
                return
    
            self._remove_button.set_visible(False)
            self._remove_button.set_sensitive(False)