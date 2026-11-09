from gi.repository import Adw
from gi.repository import Gtk, Gio, WebKit, GLib

import threading
from pathlib import Path
from ...asteria.server import DevServer 
from .sidebar import Sidebar

@Gtk.Template(resource_path='/io/github/Kriptolix/Asteria/'
              'src/gtk/ui/ProjectPage.ui')
class ProjectPage(Adw.NavigationPage):
    __gtype_name__ = 'ProjectPage'

    _sidebar = Gtk.Template.Child()
    _content = Gtk.Template.Child()    

    def __init__(self):
        super().__init__()

        self._app = Gio.Application.get_default()
        self._webview = None
    
    def _create_webview(self):

        self._webview = WebKit.WebView.new()
        self._webview.set_hexpand(True)        

        settings = WebKit.Settings.new()

        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_enable_javascript(True)
        settings.set_enable_developer_extras(True)

        self._webview.connect("context-menu", self._on_context_menu)

        self._webview.set_settings(settings)

        # self._webview.set_cors_allowlist("*") 
         
        self._content.set_child(self._webview)       

    def _on_context_menu(self, webview, context_menu, event):

        context_menu.remove_all()

        return True  # False = show, True = Hide

    def create_server(self):

        self._server = DevServer(
                    project_root=Path(self._app.project_dir.get_path()),
                    watch=False,
                    on_build=self.on_build_complete,
                    on_error=self.on_build_error
                )                
        
        threading.Thread(target=self._server.start, daemon=True).start()

    def site_rebuild(self):
        threading.Thread(target=self.dev.rebuild, daemon=True).start()

    def on_build_complete(self, result):
        print("entrou")
        GLib.timeout_add(100, self._load_preview_url)
        print("lodou")        
        GLib.idle_add(self._safe_reload_ui, result)
        print("buildou")
    
    def on_build_error(self, error):
        GLib.idle_add(self._safe_show_error, error)

    def _load_preview_url(self):
        try:
            self._webview.load_uri("http://127.0.0.1:8000")
        except Exception as e:
            print(f"Erro ao carregar URI no WebKit: {e}")
        return False # Importante: retorna False para rodar apenas uma vez

    def _safe_reload_ui(self, result):
        
        self._webview.reload()
        return False # Remove o idle_add da fila

    def _safe_show_error(self, error):
        print(f"Build error: {error}")
        return False
