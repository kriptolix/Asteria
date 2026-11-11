from gi.repository import Adw
from gi.repository import Gtk, Gio

from ...iooperations import open_with_app, list_subdirectories, list_css_files

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefTheme.ui')
class PrefTheme(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefTheme'

    _dropdown_theme = Gtk.Template.Child()
    _dropdown_variant = Gtk.Template.Child()
    _extra_button = Gtk.Template.Child()
    _i18n_button = Gtk.Template.Child()     

    def __init__(self):
        super().__init__()    

        self._app = Gio.Application.get_default()
        self._theme_selected = ""

        self._extra_button.connect("clicked", self._open_file)
        self._i18n_button.connect("clicked", self._open_file)

    def _open_file(self, button):    
        
        content_path = (self._app.project_dir.get_child("source")                          
                          .get_child("themes")
                          .get_child(self._theme_selected))   

        match button:
            case self._extra_button:
                content_path = content_path.get_child("theme.yaml")               

            case self._i18n_button:
                content_path = content_path.get_child("i18n.yaml")

        open_with_app(self._app.window, content_path) 

            
    def set_dropdown_theme(self):
        
        themes = self._app.project_dir.get_child("source").get_child("themes")
        theme_name = self._app.project_config.site.data["theme"]["name"]

        self._theme_selected = theme_name 
        
        model = list_subdirectories(themes)
        self._dropdown_theme.set_model(model)

        self.select_dropdown_item(self._dropdown_theme, theme_name)
    

    def set_dropdown_variant(self):

        theme_selected = self._dropdown_theme.get_selected_item().get_string()        
        
        variants = (self._app.project_dir.get_child("source")                  
                  .get_child("themes")
                  .get_child(theme_selected)
                  .get_child("css"))

        variant_name = self._app.project_config.theme.data["default_variant"]        
        
        model = list_css_files(variants)
        
        self._dropdown_variant.set_model(model)

        self.select_dropdown_item(self._dropdown_variant, variant_name)

    
    def select_dropdown_item(self, dropdown: Gtk.DropDown, value: str):
        
        model = dropdown.get_model()

        for i in range(model.get_n_items()):
            if model.get_string(i) == value:
                dropdown.set_selected(i)                
                return True
                    
        return False

    def get_theme(self):

        site_config = self._app.project_config.site.data
        theme_config = self._app.project_config.theme.data

        site_config["theme"]["name"] = self._dropdown_theme.get_selected_item().get_string()
        theme_config["default_variant"] = self._dropdown_variant.get_selected_item().get_string()



    