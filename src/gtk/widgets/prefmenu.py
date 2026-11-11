from gi.repository import Adw
from gi.repository import Gtk, Gdk, GObject, Gio

from .itemmenu import ItemMenu

from ...iooperations import choose_file

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefMenu.ui')
class PrefMenu(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefMenu'

    _add_button = Gtk.Template.Child()
    _blog_button = Gtk.Template.Child()
    _trash_button = Gtk.Template.Child()
    _menu_list = Gtk.Template.Child()    

    def __init__(self):
        super().__init__()

        self._drag_coords = [0, 0]
        self._app = Gio.Application.get_default()        

        self._add_button.connect("clicked", self._add_page_button)
        self._blog_button.connect("clicked", self._add_blog_button)

        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_trash_drop)

        self._trash_button.add_controller(drop_target)    


    def set_menu(self):  # adicionar verificação se o item existe
        
        menu = self._app.project_config.site.data["menu"]

        print("menu list: ", menu)        

        for item in menu:
            self._add_page(item)


    def get_menu(self):

        config = self._app.project_config.site.data
        menu = []

        row = self._menu_list.get_first_child()

        while row:
            
            menu.append(row.get_title())
            row = row.get_next_sibling()
        
        config["menu"] = menu


    def _add_blog_button(self, button):
        self._add_page("blog")


    def _add_page_button(self, button):

        def on_chosen(gfile):
            if gfile:
                name = gfile.get_basename().rsplit('.', 1)[0]
                self._add_page(name)                

        ###          
       
        pages = self._app.project_dir.get_child("source").get_child("content").get_child("pages")

        choose_file(self._app.window, on_chosen, pages)


    def _add_page(self, name):
        
        widget = ItemMenu(name)
        self._menu_list. append(widget)

        drop_controller = Gtk.DropControllerMotion()
        drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)        

        drag_source.connect("prepare", self._on_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)
        drop_target.connect("drop", self._on_drop)

        widget._drag_image.add_controller(drag_source)
        widget.add_controller(drop_target)
        widget.add_controller(drop_controller) 
    
    
    def _on_prepare(self, source, x, y):

        self._drag_coords[0] = x
        self._drag_coords[1] = y

        row = source.get_widget().get_ancestor(Gtk.ListBoxRow)

        value = GObject.Value()
        value.init(Gtk.ListBoxRow)
        value.set_object(row)

        return Gdk.ContentProvider.new_for_value(value)


    def _on_drag_begin(self, source, drag_object):

        widget = source.get_widget().get_ancestor(Gtk.ListBoxRow)
        title = widget.get_title()      

        drag_widget = ItemMenu(title)        

        icon = Gtk.DragIcon.get_for_drag(drag_object)
        icon.set_child(drag_widget)

        drag_object.set_hotspot(self._drag_coords[0], self._drag_coords[1])
          

    def _on_drop(self, drop, drag_target, x, y):      

        target_row = drop.get_widget()
        source_row = drag_target       

        if not source_row or not target_row or source_row == target_row:
            return False

        position = target_row.get_index()             

        self._menu_list.remove(source_row)  
        self._menu_list.insert(source_row, position)

        return True


    def _on_trash_drop(self, drop, source_row, x, y):
    
        if not source_row:
            return False

        self._menu_list.remove(source_row)

        return True