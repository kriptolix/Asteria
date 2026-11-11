from gi.repository import Adw
from gi.repository import Gtk, Gio

from pathlib import Path

from ...iooperations import choose_file

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefSite.ui')
class PrefSite(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefSite'

    _site_title = Gtk.Template.Child()
    _site_url = Gtk.Template.Child()    
    _site_description = Gtk.Template.Child()
    _choose_button = Gtk.Template.Child()
    _blog_button = Gtk.Template.Child()
    _site_home = Gtk.Template.Child()
    _site_lang = Gtk.Template.Child()
    _expander = Gtk.Template.Child()       

    def __init__(self):
        super().__init__()

        self._app = Gio.Application.get_default()
        self._config = None        

        self.title_buffer = self._site_title.get_buffer()
        self.url_buffer = self._site_url.get_buffer()
        self.desc_buffer = self._site_description.get_buffer()
        self.home_buffer = self._site_home.get_buffer()
        self.lang_buffer = self._site_lang.get_buffer()

        self._choose_button.connect("clicked", self._set_home_button)
        self._blog_button.connect("clicked", self._set_home_button)


    def _set_home_button(self, button):

        def _on_chosen(gfile):
            basename = gfile.get_basename()
            name = Path(basename).stem
            self.home_buffer.set_text(name, -1)

        if button == self._blog_button:
            self.home_buffer.set_text("blog", -1)
            return
        
        pages = self._app.project_dir.get_child("source").get_child("content").get_child("pages")

        choose_file(self._app.window, _on_chosen, pages)        

    def set_site_config(self):

        self._config = self._app.project_config.site.data["site"]        

        self.title_buffer.set_text(self._config["title"], -1)
        self.url_buffer.set_text(self._config["url"], -1)
        self.home_buffer.set_text(self._config["home_page"], -1)
        self.lang_buffer.set_text(self._config["language"], -1)

    def get_site_config(self):

        self._config["title"] = self.title_buffer.get_text()
        self._config["url"] = self.url_buffer.get_text() 
        self._config["home_page"] = self.home_buffer.get_text() 
        self._config["language"] = self.lang_buffer.get_text()

            

   
      