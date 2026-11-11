from gi.repository import Adw
from gi.repository import Gtk, Gdk, GObject, Gio

from .itemsocial import ItemSocial

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/PrefSocial.ui')
class PrefSocial(Adw.PreferencesGroup):
    __gtype_name__ = 'PrefSocial'

    _add_button = Gtk.Template.Child()
    _trash_button = Gtk.Template.Child()
    _social_list = Gtk.Template.Child()        

    def __init__(self):
        super().__init__()

        self._drag_coords = [0, 0]
        self._app = Gio.Application.get_default()        

        self._add_button.connect("clicked", self._add_link_button)

        drop_target = Gtk.DropTarget.new(Gtk.ListBoxRow, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_trash_drop)

        self._trash_button.add_controller(drop_target)
        

    def set_social(self):  # adicionar verificação se o item existe
        
        social = self._app.project_config.site.data["social"]        

        for item in social:
            widget = ItemSocial()
            widget.set_url(item["url"])
            widget.set_label(item["label"])
            widget.set_platform(item["platform"]) 
            self._add_link(widget)

    def get_social(self):

        social = []

        row = self._social_list.get_first_child()

        while row:            

            social.append({
                "platform": row.get_platform(),
                "url": row.get_url(),
                "label": row.get_label()
            })

            row = row.get_next_sibling()

        self._app.project_config.site.data["social"] = social
         

    def _add_link_button(self, button):

        widget = ItemSocial()
        self._add_link(widget)

    def _add_link(self, widget):
        
        self._social_list.append(widget)        

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
        
        drag_widget = ItemSocial()        

        drag_widget.set_label(widget.get_label())
        drag_widget.set_url(widget.get_url())
        drag_widget.set_platform(widget.get_platform())        

        icon = Gtk.DragIcon.get_for_drag(drag_object)
        icon.set_child(drag_widget)

        drag_object.set_hotspot(self._drag_coords[0], self._drag_coords[1])
          

    def _on_drop(self, drop, drag_target, x, y):

        target_row = drop.get_widget()
        source_row = drag_target       

        if not source_row or not target_row or source_row == target_row:
            return False

        position = target_row.get_index()

        self._social_list.remove(source_row)
        self._social_list.insert(source_row, position)

        return True

    def _on_trash_drop(self, drop, source_row, x, y):

        if not source_row:
            return False

        self._social_list.remove(source_row)

        return True