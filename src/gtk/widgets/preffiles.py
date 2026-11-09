from gi.repository import Adw
from gi.repository import Gtk, Gio

from ...iooperations import open_with_app


@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefFiles.ui')
class PrefFiles(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefFiles'

    _page_button = Gtk.Template.Child()
    _post_button = Gtk.Template.Child() 
    _cover_button = Gtk.Template.Child()     

    def __init__(self):
        super().__init__()
  
        self._page_button.connect("clicked", self.open_dir)
        self._post_button.connect("clicked", self.open_dir)
        self._cover_button.connect("clicked", self.open_dir)

        self._app = Gio.Application.get_default()

    def open_dir(self, button):
        
        content_path = None    

        match button:
            case self._page_button:
                content_path = self._app.project_dir.get_child("source").get_child("content").get_child("pages")

            case self._post_button:
                content_path = self._app.project_dir.get_child("source").get_child("content").get_child("posts")

            case self._cover_button:
                content_path = self._app.project_dir.get_child("source").get_child("static").get_child("covers")

        open_with_app(self._app.window, content_path)


    