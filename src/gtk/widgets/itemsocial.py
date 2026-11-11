from gi.repository import Adw
from gi.repository import Gtk

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ItemSocial.ui')
class ItemSocial(Adw.ActionRow):
    __gtype_name__ = 'ItemSocial'

    _platform = Gtk.Template.Child()
    _url = Gtk.Template.Child()
    _label = Gtk.Template.Child()
    _drag_image = Gtk.Template.Child()    

    def __init__(self):
        super().__init__()

        self._url_buffer = self._url.get_buffer()
        self._label_buffer = self._label.get_buffer()

        self._drag_image.set_cursor_from_name("grab")   

        self._platform_labels = ["Custom", "Discord", "E-mail", "Facebook", "GitHub", "GitLab", "Gmail", 
                                 "Instagram", "Mastodon", "RSS", "Telegram", "X", "Youtube", ]     
        
        self._platform_values = ["custom", "discord", "e-mail", "facebook", "github", "gitlab", "gmail",
                                 "instagram", "mastodon", "rss", "telegram", "x", "youtube",]

        self._platform_model = Gtk.StringList.new(self._platform_labels)
        self._platform.set_model(self._platform_model)

    def set_url(self, url: str) -> None:         
        self._url_buffer.set_text(url, -1)


    def set_label(self, label: str) -> None:
        self._label_buffer.set_text(label, -1)


    def set_platform(self, platform: str)-> None:
    
            for item in range(self._platform_model.get_n_items()):
                if self._platform_model.get_string(item) == self._platform_labels[self._platform_values.index(platform)]:
                    self._platform.set_selected(item)


    def get_url(self) -> str:
        return self._url_buffer.get_text()
              
    
    def get_label(self) -> str:
        return self._label_buffer.get_text()
       
        
    def get_platform(self) -> str:

        selected = self._platform.get_selected_item().get_string()
        return self._platform_values[self._platform_labels.index(selected)]
                    
                
                    
        


                