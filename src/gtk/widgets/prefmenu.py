from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefMenu.ui')
class PrefMenu(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefMenu'    

    def __init__(self):
            super().__init__()