from gi.repository import Gtk, Adw
from gettext import gettext as _


@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/MessageDialog.ui')
class MessageDialog(Adw.MessageDialog):

    __gtype_name__ = 'MessageDialog'

    def __init__(self, window, type, data=None):

        super().__init__()

        self.set_transient_for(window)
        self.body = ""
        self.heading = ""
        self.data = data

        match type:
            case "create_project":
                self._create_project()
            case "save_project":
                self._save_project()
            case "recover_unsaved":
                self._recovery_unsaved()
            case "remove_section":
                self._remove_section()            

        self.set_body(self.body)
        self.set_heading(self.heading)
        self.present()

    def _remove_section(self):

        self.add_response("cancel",  _("_Cancel"))
        self.add_response("delete",    _("_Delete"))

        self.set_response_appearance("delete", 2)

        self.heading = _("Delete section?")
        self.body = _("Delete this section will remove "
                         "all sub sections of this section and "
                         "the text attached to them")    

    def _create_project(self):

        def enter_key_pressed(widget):

            self.response("create")
            self.close()

        def avoid_empty_name(buffer, length):

            if (buffer.get_length() > 0):
                self.set_response_enabled("create", True)
            else:
                self.set_response_enabled("create", False)

        ##

        builder = Gtk.Builder.new_from_resource(
            '/io/github/Kriptolix/Asteria/src/gtk/ui/DialogCreate.ui'
        )

        self.box = builder.get_object("DialogCreate")

        self.entry_name = builder.get_object("_entry_name") 
        self.entry_path = builder.get_object("_entry_path")

        self.set_child(self.box)   

        self.buffer = self.entry_name.get_buffer()

        self.add_response("cancel",  _("_Cancel"))
        self.add_response("create",    _("_Create"))
        self.set_response_appearance("create", 1)
        self.set_default_response("cancel")
        self.set_response_enabled("create", False)

        self.heading = _("Project Title")

        self._name.set_input_hints(Gtk.InputHints.NONE)
        self._name.set_input_purpose(Gtk.InputPurpose.FREE_FORM)

        self._name.connect("activate", enter_key_pressed)
        self.buffer.connect("notify::length", avoid_empty_name)

    def _save_project(self):

        self.add_response("cancel",  _("_Cancel"))
        self.add_response("discard",    _("_Discard"))
        self.add_response("save",    _("_Save"))

        self.heading = _("Save current project?")
        self.body = _("There are unsaved changes to the current project"
                         ". If these changes are not saved, they will be "
                         "lost. Do you want to save these changes?")

        self.set_response_appearance("discard", 2)
        self.set_response_appearance("save", 1)

    def _recover_unsaved(self):

        gfile = self.data
        base_name = gfile.get_basename()
        name = base_name[8:-15]

        self.add_response("discard",    _("_Discard"))
        self.add_response("open",    _("_Open"))

        self.set_response_appearance("discard", 2)
        self.set_response_appearance("open", 1)

        self.heading = _("Recover file finded")
        self.body = _(f"There are unsaved changes to project: {name}. "
                         "Do you want to open the recovered file?")