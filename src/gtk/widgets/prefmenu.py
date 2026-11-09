from gi.repository import Adw
from gi.repository import Gtk, Gdk, GObject, Gio

from .itemmenu import ItemMenu

from ...iooperations import choose_file

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefMenu.ui')
class PrefMenu(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefMenu'

    _add_button = Gtk.Template.Child()
    _menu_list = Gtk.Template.Child()    

    def __init__(self):
        super().__init__()

        self._drag_coords = [0, 0]
        self._app = Gio.Application.get_default()        

        self._add_button.connect("clicked", self._add_page_button)    


    def set_menu(self):  # adicionar verificação se o item existe
        menu = self._app.project_config.site.data["menu"]        

        for item in menu:
            self._add_page(item['page'])

    def _add_page_button(self, button):

        def on_chosen(gfile):
            if gfile:
                name = gfile.get_basename()
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

        widget.add_controller(drag_source)
        widget.add_controller(drop_target)
        widget.add_controller(drop_controller)

        drag_source.connect("prepare", self._on_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)  

        drop_target.connect("drop", self._on_drop) 
    
    
    def _on_prepare(self, source, x, y):

        self._drag_coords[0] = x
        self._drag_coords[1] = y

        row = source.get_widget()

        value = GObject.Value()
        value.init(Gtk.ListBoxRow)
        value.set_object(row)

        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(self, source, drag_object):

        row = source.get_widget()
        title = row.get_title()      

        drag_widget = ItemMenu(title)

        icon = Gtk.DragIcon.get_for_drag(drag_object)
        icon.set_child(drag_widget)

        drag_object.set_hotspot(self._drag_coords[0], self._drag_coords[1])
          

    def _on_drop(self, drop, drag_target, x, y):      

        drop_target = drop.get_widget()

        if (not drag_target or not drop_target
                or drag_target == drop_target):

            return False         
        
        source_row = drag_target
        target_row = drop_target              

        self._menu_list.remove(source_row)   
        
        position = target_row.get_index()                 

        self._menu_list.insert(source_row, position)       

        return True