from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ItemMenu.ui')
class ItemMenu(Adw.PreferencesGroup):
    __gtype_name__ = 'ItemMenu'    

    def __init__(self, title, subtitle):
            super().__init__()

            self.set_title(title)
            self.set_subtitle(subtitle)

            self._motion = Gtk.EventControllerMotion.new()
            self._motion.connect("enter", self._on_mouse_move)
            self._motion.connect("leave", self._on_mouse_move)
            self.add_controller(self._motion)

    def _on_mouse_move(self, motion, x=None, y=None):        
            
            if x and y:
                self._trash_button.set_visible(True)
                self._trash_button.set_sensitive(True)
                return
    
            self._trash_button.set_visible(False)
            self._trash_button.set_sensitive(False)