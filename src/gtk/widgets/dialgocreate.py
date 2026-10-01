from gi.repository import Gtk, Adw
from gettext import gettext as _

from ...iooperations import choose_directory

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/DialogCreate.ui')
class DialogCreate(Adw.Dialog):

    __gtype_name__ = 'DialogCreate'

    _create_button = Gtk.Template.Child()
    _cancel_button = Gtk.Template.Child()
    _load_button = Gtk.Template.Child()
    _entry_name = Gtk.Template.Child()
    _entry_path = Gtk.Template.Child()

    def __init__(self, window, callback):

        super().__init__()

        self._callback = callback

        self._folder_path = ""
        
        self._cancel_button.connect("clicked", lambda *_: self.close())
        self._load_button.connect("clicked", self._get_path)
        self._create_button.connect("clicked", self.setup_path)

        self.window = window

        self._name_buffer = self._entry_name.get_buffer()
        self._path_buffer = self._entry_path.get_buffer()
       
        self._name_buffer.connect("notify::length", self._avoid_empty_name)        
        self._path_buffer.connect("notify::length", self._avoid_empty_name)

    def _avoid_empty_name(self, buffer, length):

        if (self._name_buffer.get_length() > 0 
            and self._path_buffer.get_length() > 0):

            self._create_button.set_sensitive(True) 
        else:
            self._create_button.set_sensitive(False)  

    def _get_path(self, button):
        
        choose_directory(self.window, self._entry_path)

    def setup_path(self, button):
        folder_name = self._entry_name.get_text()
        folder_directory = self._entry_path.get_text()
        folder_path = f"{folder_directory}/{folder_name}"

        self._callback(folder_path)
        

        self.close()





        

    