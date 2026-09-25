from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefFiles.ui')
class PrefFiles(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefFiles'    

    def __init__(self):
            super().__init__()