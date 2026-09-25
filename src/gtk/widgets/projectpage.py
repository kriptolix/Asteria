from gi.repository import Adw
from gi.repository import Gtk

from .sidebar import Sidebar

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ProjectPage.ui')
class ProjectPage(Adw.NavigationPage):
    __gtype_name__ = 'ProjectPage'

    _project_view = Gtk.Template.Child()
    _content_view = Gtk.Template.Child()

    def __init__(self):
            super().__init__()