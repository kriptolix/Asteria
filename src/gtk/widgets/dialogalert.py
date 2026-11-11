from gi.repository import Gtk, Adw
from gettext import gettext as _

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/DialogAlert.ui')
class DialogAlert(Adw.Dialog):

    __gtype_name__ = 'DialogAlert'

    def __init__(self, window):
        super().__init__()

        