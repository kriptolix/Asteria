from gi.repository import Adw
from gi.repository import Gtk

from .prefsite import PrefSite
from .preffiles import PrefFiles
from .prefmenu import PrefMenu
from .preftheme import PrefTheme
from .prefsocial import PrefSocial

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/Sidebar.ui')
class Sidebar(Adw.NavigationPage):
    __gtype_name__ = 'Sidebar'

    _update_button = Gtk.Template.Child()
    _close_button = Gtk.Template.Child()
    _pref_site = Gtk.Template.Child()
    _pref_theme = Gtk.Template.Child()
    _pref_files = Gtk.Template.Child()
    _pref_menu = Gtk.Template.Child()
    _pref_social = Gtk.Template.Child()    

    def __init__(self):
        super().__init__()

        self._close_button.set_action_name("app.quit")


    def set_config(self):
        
        self._pref_site.set_site_config()
        self._pref_theme.set_dropdown_theme()
        self._pref_theme.set_dropdown_variant()
        self._pref_menu.set_menu()