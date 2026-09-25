from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefTheme.ui')
class PrefTheme(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefTheme'    

    def __init__(self):
            super().__init__()