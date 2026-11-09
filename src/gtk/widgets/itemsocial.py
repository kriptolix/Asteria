from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ItemScial.ui')
class ItemMenu(Adw.ActionRow):
    __gtype_name__ = 'ItemMenu'

    _platform = Gtk.Template.Child()
    _url = Gtk.Template.Child()
    _label = Gtk.Template.Child()    

    def __init__(self):
            super().__init__()            