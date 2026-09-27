from gi.repository import Adw
from gi.repository import Gtk, Gio

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefFiles.ui')
class PrefFiles(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefFiles'    

    def __init__(self):
            super().__init__()
  

    def open_folder(_button):
        folder = Gio.File.new_for_path("/caminho/da/pasta")
        Gio.AppInfo.launch_default_for_uri(folder.get_uri(), None)

    def open_file(_button):
        folder = Gio.File.new_for_path("/caminho/do/arquivo")
        Gio.AppInfo.launch_default_for_uri(folder.get_uri(), None)