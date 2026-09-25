from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefNav.ui')
class PrefNav(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefNav'    

    def __init__(self):
            super().__init__()