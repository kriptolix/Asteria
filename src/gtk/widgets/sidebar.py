from gi.repository import Adw
from gi.repository import Gtk

from .prefsite import PrefSite
from .preffiles import PrefFiles
from .prefmenu import PrefMenu
from .preftheme import PrefTheme
from .prefnav import PrefNav

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/Sidebar.ui')
class Sidebar(Adw.NavigationPage):
    __gtype_name__ = 'Sidebar'    

    def __init__(self):
            super().__init__()