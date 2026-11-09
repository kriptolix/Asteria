from gi.repository import Adw
from gi.repository import Gtk, Gdk, GObject, Gio


@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefSocial.ui')
class PrefSocial(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefSocial'

    _add_button = Gtk.Template.Child()
    _social_list = Gtk.Template.Child()        

    def __init__(self):
        super().__init__()

        self._drag_coords = [0, 0]
        self._app = Gio.Application.get_default()        

        self._add_button.connect("clicked", self._add_link_button)    


    def set_social(self):  # adicionar verificação se o item existe
        
        social = self._app.project_config.site.data["social"]

        for item in social:
            self._add_link(item)

    def _add_link_button(self, button):

        pass

    def _add_link(self, name):
        
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