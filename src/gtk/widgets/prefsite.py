from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefSite.ui')
class PrefSite(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefSite'    

    def __init__(self):
            super().__init__()