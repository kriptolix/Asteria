from gi.repository import Adw
from gi.repository import Gtk, Gio

from .prefsite import PrefSite
from .preffiles import PrefFiles
from .prefmenu import PrefMenu
from .preftheme import PrefTheme
from .prefsocial import PrefSocial


@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/MainMenu.ui')
class MainMenu(Gtk.PopoverMenu):

    __gtype_name__ = 'MainMenu'

    def __init__(self):
        super().__init__()


@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/Sidebar.ui')
class Sidebar(Adw.NavigationPage):
    __gtype_name__ = 'Sidebar'

    _update_button = Gtk.Template.Child()
    _close_button = Gtk.Template.Child()
    _menu_button = Gtk.Template.Child()
    _new_button = Gtk.Template.Child()
    _open_button = Gtk.Template.Child()
    _preferences = Gtk.Template.Child()
    _pref_site = Gtk.Template.Child()
    _pref_theme = Gtk.Template.Child()
    _pref_files = Gtk.Template.Child()
    _pref_menu = Gtk.Template.Child()
    _pref_social = Gtk.Template.Child()    

    def __init__(self):
        super().__init__()

        self._app = Gio.Application.get_default()
        self._menu = MainMenu()

        self._close_button.set_action_name("app.quit")
        self._open_button.set_action_name("app.open")
        self._new_button.set_action_name("app.new")

        self._menu_button.set_popover(self._menu)
        self._update_button.connect("clicked", self._app.update_project)


    def set_config(self) -> None:
        
        self._pref_site.set_site_config()
        self._pref_theme.set_dropdown_theme()
        self._pref_theme.set_dropdown_variant()
        self._pref_menu.set_menu()
        print("1")
        self._pref_social.set_social()
        print("2")

        self._preferences.set_sensitive(True)
        self._update_button.set_sensitive(True)
        self._pref_site._expander.set_expanded(True)

    def get_config(self)-> None:

        self._pref_menu.get_menu()
        self._pref_social.get_social()
        self._pref_site.get_site_config()
        self._pref_theme.get_theme()
