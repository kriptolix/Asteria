from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ItemMenu.ui')
class ItemMenu(Adw.ActionRow):
    __gtype_name__ = 'ItemMenu'

    
    _drag_image = Gtk.Template.Child()    

    def __init__(self, title):
        super().__init__()

        self.set_title(title)
        self._drag_image.set_cursor_from_name("grab")

    def get_entry(self):

        return self.get_title()