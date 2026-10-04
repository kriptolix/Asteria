"""
Local development server.

This module has two layers:

  * `DevServer` -- a non-blocking class. `start()` runs the initial
    build, serves it over HTTP, and (optionally) watches for changes,
    all in background threads, then returns immediately. Every build
    result / error / detected change is reported through the callbacks
    passed to its constructor instead of being printed. This is what a
    GUI (or api.py, or any other non-terminal frontend) should use.

  * `serve()` -- the CLI's own entry point. It's a thin, blocking
    wrapper around DevServer that reproduces the exact terminal output
    `asteria serve` has always printed, and returns only once the user
    hits Ctrl+C. Kept exactly for that reason: cli.py's contract (prints
    to stdout/stderr, blocks, returns an int exit code) doesn't change.

Automatic rebuild on file changes uses the optional `watchfiles` package
(`pip install "asteria[watch]"`). Without it the server still works; it
just doesn't watch. A frontend that has its own file watcher (e.g. a GTK
app using Gio.FileMonitor) doesn't need `watchfiles` at all: it creates
the DevServer with `watch=False, live_reload=True` and calls
`DevServer.rebuild()` whenever its own watcher detects a change.
"""

from __future__ import annotations

import functools
import http.server
import importlib.util
import socketserver
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .build import BuildResult, run_build
from .config import load_config
from .errors import AsteriaError

LIVE_RELOAD_ENDPOINT = "/__asteria_live_reload__"

LIVE_RELOAD_SCRIPT = f"""
<script>
(function() {{
  function connect() {{
    var es = new EventSource("{LIVE_RELOAD_ENDPOINT}");
    es.onmessage = function(ev) {{
      if (ev.data === "reload") {{ location.reload(); }}
    }};
    es.onerror = function() {{ es.close(); setTimeout(connect, 1000); }};
  }}
  connect();
}})();
</script>
""".strip()


def _print_result(result: BuildResult, prefix: str = "Build") -> None:
    for diag in result.diagnostics:
        print(diag)
    if result.success:
        print(f"{prefix} ok ({len(result.generated_files)} file(s)).")
    else:
        print(
            f"{prefix} com {len(result.diagnostics.errors)} error(s) — "
            "serving what already exists on disk.",
            file=sys.stderr,
        )


class ReloadBroadcaster:
    """Generation counter + condition, used by SSE handlers to determine
        when a new rebuild has occurred.."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._generation = 0

    def notify_reload(self) -> None:
        with self._condition:
            self._generation += 1
            self._condition.notify_all()

    def current_generation(self) -> int:
        with self._condition:
            return self._generation

    def wait_for_change(self, last_seen: int, timeout: float) -> int:
        with self._condition:
            if self._generation != last_seen:
                return self._generation
            self._condition.wait(timeout)
            return self._generation


class _DevServerHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files normally, plus an SSE endpoint for
        live reload."""

    def do_GET(self) -> None:  # noqa: N802 (name required by the stdlib)
        if self.path == LIVE_RELOAD_ENDPOINT:
            self._handle_sse()
            return
        super().do_GET()

    def _handle_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        broadcaster: ReloadBroadcaster = self.server.broadcaster  # type: ignore[attr-defined]
        last_seen = broadcaster.current_generation()
        try:
            while True:
                new_gen = broadcaster.wait_for_change(last_seen, timeout=25)
                if new_gen != last_seen:
                    self.wfile.write(b"data: reload\n\n")
                    last_seen = new_gen
                else:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if args and "__asteria_live_reload__" in str(args[0]):
            return  # avoid cluttering the log with the long-lived SSE connection
        sys.stderr.write(f"  {self.address_string()} - {args[0] if args else ''}\n")


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def _start_http_server(output_dir: Path, host: str, port: int) -> _Server:
    handler = functools.partial(_DevServerHandler, directory=str(output_dir))
    httpd = _Server((host, port), handler)
    httpd.broadcaster = ReloadBroadcaster()  # type: ignore[attr-defined]
    return httpd


def watch_backend_available() -> bool:
    """Whether the optional `watchfiles` package is installed, i.e.
    whether DevServer's built-in file watching can work. Cheap: it only
    looks the package up, it doesn't import it."""
    return importlib.util.find_spec("watchfiles") is not None


def discover_watch_paths(project_root: Path, existing_only: bool = True) -> list[Path]:
    """Returns the paths a file watcher should observe for this project.

    Public so that a frontend with its own watcher (e.g. Gio.FileMonitor
    in a GTK app) watches exactly what the built-in one would.

    By default only paths that exist right now are returned. With
    `existing_only=False` the full candidate list comes back regardless,
    so a watcher can keep tracking a directory that gets deleted and
    recreated, or created for the first time after the watcher started.

    Mirrors run_build's own path resolution (project_root / "source" /
    config_filename): all editable project files -- content, static
    assets, site.yaml -- live under source/, not directly under
    project_root.

    The active theme's directory is included too -- SiteConfig.theme_dir
    combines `theme.directory` and `theme.name` from site.yaml (falling
    back to Asteria's own bundled theme when the project doesn't have
    its own), so this follows whatever the site is actually configured
    to use instead of a fixed guess at `source/themes`. Failing to read
    site.yaml here (AsteriaError) just means the theme directory is
    skipped -- the caller already loaded it once for the initial build,
    so this is defensive only.
    """
    source_dir = project_root / "source"
    watch_paths = [
        p
        for p in [
            source_dir / "content",
            source_dir / "static",
            source_dir / "site.yaml",
        ]
        if not existing_only or p.exists()
    ]
    try:
        theme_dir = load_config(source_dir / "site.yaml").theme_dir
        if not existing_only or theme_dir.exists():
            watch_paths.append(theme_dir)
    except AsteriaError:
        pass
    return watch_paths


@dataclass
class DevServerStatus:
    """A snapshot of a DevServer's current state -- cheap to build, safe
    to poll from any thread (e.g. a GUI updating a status bar)."""

    running: bool
    host: str
    port: int
    output_dir: Path | None
    watching: bool


class DevServer:
    """Non-blocking dev server: builds the project, serves the output
    over HTTP, and (optionally) rebuilds on file changes -- all in
    background threads, so `start()` returns immediately and callers
    (a GUI event loop, a script, cli.py's own blocking `serve()`) stay
    in control.

    Every build result / fatal error / detected file change is reported
    through the `on_*` callbacks passed to the constructor, instead of
    being printed -- a frontend renders those however it wants.

    Threading note: the callbacks run on Asteria's own background
    threads (the initial call inside `start()`, and later ones from the
    file-watcher thread), never on the thread that called `start()`. A
    GTK4/GLib-based UI must NOT touch GTK widgets directly from inside a
    callback -- marshal back to the main loop first, e.g.:

        def on_build(result):
            GLib.idle_add(update_status_label, result)

    Typical use:

        dev = DevServer(project_root, on_build=..., on_error=...)
        dev.start()
        ...
        dev.stop()

    Using your own file watcher (no `watchfiles` needed):

        dev = DevServer(project_root, watch=False, live_reload=True)
        dev.start()                 # blocks during the initial build!
        ...
        dev.rebuild()               # call whenever your watcher fires

    `start()` and `rebuild()` are blocking (they run a full build), so a
    GUI should call them from a worker thread.
    """

    def __init__(
        self,
        project_root: Path,
        host: str = "127.0.0.1",
        port: int = 8000,
        converter_name: str = "auto",
        watch: bool = True,
        live_reload: bool | None = None,
        on_build: Callable[[BuildResult], None] | None = None,
        on_error: Callable[[AsteriaError], None] | None = None,
        on_change: Callable[[int], None] | None = None,
        on_watch_start: Callable[[list[Path]], None] | None = None,
    ) -> None:
        """
        watch: use the built-in file watcher to rebuild automatically.
            Needs the optional `watchfiles` package; if it isn't
            installed this silently becomes False (check
            `watch_backend_available()` beforehand to warn the user).
        live_reload: inject the live-reload script into generated pages
            and let `rebuild()` refresh connected browsers. Defaults to
            whatever `watch` ended up being. Pass True together with
            watch=False when an external watcher calls `rebuild()`.
        on_build: called with the BuildResult after every successful
            build (the initial one, and every rebuild).
        on_error: called with the AsteriaError when a build fails
            fatally (bad site.yaml, missing theme, ...) or the HTTP port
            can't be bound.
        on_change: called with the number of changed files right before
            a rebuild is triggered by the file watcher.
        on_watch_start: called once, with the list of paths being
            watched, right after watching actually starts. Not called at
            all if there's nothing to watch, or if watch=False.
        """
        self.project_root = project_root
        self.host = host
        self.port = port
        self.converter_name = converter_name
        # Built-in watching is only possible when watchfiles is installed.
        self.watch = watch and watch_backend_available()
        self.live_reload = self.watch if live_reload is None else live_reload
        self._on_build = on_build
        self._on_error = on_error
        self._on_change = on_change
        self._on_watch_start = on_watch_start

        self._httpd: _Server | None = None
        self._http_thread: threading.Thread | None = None
        self._watch_thread: threading.Thread | None = None
        self._watch_stop = threading.Event()
        # Serializes builds: the built-in watcher and an external one
        # (or the initial build in start()) must never run two at once.
        self._build_lock = threading.Lock()
        self._last_result: BuildResult | None = None

    @property
    def last_result(self) -> BuildResult | None:
        """The most recent BuildResult (initial build or last rebuild),
        or None if `start()` hasn't successfully built yet."""
        return self._last_result

    @property
    def output_dir(self) -> Path | None:
        return self._last_result.output_dir if self._last_result else None

    @property
    def is_running(self) -> bool:
        return self._httpd is not None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def status(self) -> DevServerStatus:
        return DevServerStatus(
            running=self.is_running,
            host=self.host,
            port=self.port,
            output_dir=self.output_dir,
            watching=self._watch_thread is not None and self._watch_thread.is_alive(),
        )

    def _build(self) -> BuildResult | None:
        live_reload_script = LIVE_RELOAD_SCRIPT if self.live_reload else None
        with self._build_lock:
            try:
                result = run_build(
                    self.project_root,
                    converter_name=self.converter_name,
                    live_reload_script=live_reload_script,
                )
            except AsteriaError as exc:
                # Callbacks run outside the lock so a slow or re-entrant
                # callback can never block (or deadlock) other builds.
                error: AsteriaError | None = exc
                result = None
            else:
                error = None
                self._last_result = result

        if error is not None:
            if self._on_error:
                self._on_error(error)
            return None
        if self._on_build:
            self._on_build(result)
        return result

    def rebuild(self) -> BuildResult | None:
        """Rebuilds the site and, if the build succeeded, tells connected
        browsers to reload. Meant to be called by an external file
        watcher (see the class docstring); the built-in watcher uses it
        too.

        Blocking -- call it from a worker thread in a GUI. Returns None
        after reporting via `on_error` if the build failed fatally;
        content-level errors still yield a BuildResult, as in `start()`.
        """
        result = self._build()
        if result is not None:
            self.reload_browsers()
        return result

    def reload_browsers(self) -> None:
        """Tells every browser connected to the live-reload endpoint to
        refresh. No-op if the HTTP server isn't running."""
        if self._httpd is not None:
            self._httpd.broadcaster.notify_reload()  # type: ignore[attr-defined]

    def start(self) -> bool:
        """Runs the initial build and starts serving it.

        Returns False (after reporting via on_error) if the initial
        build failed fatally, or if the HTTP port couldn't be bound.
        Returns True otherwise -- even if the build produced content
        errors, as long as there's an output_dir to serve, matching the
        CLI's long-standing "serve what already exists on disk" behavior.
        Calling start() while already running is a no-op that returns
        True.
        """
        if self.is_running:
            return True

        result = self._build()
        if result is None:
            return False

        try:
            self._httpd = _start_http_server(result.output_dir, self.host, self.port)
        except OSError as exc:
            self._httpd = None
            if self._on_error:
                self._on_error(AsteriaError(f"Could not open {self.host}:{self.port} — {exc}"))
            return False

        self._http_thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._http_thread.start()

        if self.watch:
            self._start_watching()

        return True

    def _start_watching(self) -> None:
        watch_paths = discover_watch_paths(self.project_root)
        if not watch_paths:
            return

        self._watch_stop.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_loop, args=(watch_paths,), daemon=True
        )
        self._watch_thread.start()
        if self._on_watch_start:
            self._on_watch_start(watch_paths)

    def _watch_loop(self, watch_paths: list[Path]) -> None:
        from watchfiles import watch as watchfiles_watch

        # stop_event lets stop() end this generator promptly (rather
        # than relying on the thread being daemonic and only dying with
        # the whole process), so a GUI can start/stop the dev server
        # repeatedly in one session.
        for changes in watchfiles_watch(*watch_paths, stop_event=self._watch_stop):
            if self._watch_stop.is_set():
                break
            if self._on_change:
                self._on_change(len(changes))
            self.rebuild()

    def stop(self) -> None:
        """Stops the file watcher (if any) and the HTTP server, and
        waits (briefly) for their threads to actually exit. Safe to call
        even if `start()` was never called or already failed."""
        self._watch_stop.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=2)
            self._watch_thread = None

        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._http_thread is not None:
            self._http_thread.join(timeout=2)
            self._http_thread = None


def serve(
    project_root: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    converter_name: str = "auto",
    watch: bool = True,
) -> int:
    """CLI entry point for `asteria serve`: blocks until Ctrl+C, printing
    exactly what it always has. Implemented on top of DevServer -- any
    other frontend should use DevServer directly instead of this
    function, since this one blocks and only communicates through
    stdout/stderr and an exit code.
    """
    # DevServer would silently disable watching without watchfiles; the
    # CLI, unlike a GUI, should tell the user why and how to fix it.
    watch_missing = watch and not watch_backend_available()
    if watch_missing:
        watch = False

    state = {"first_build": True}

    def on_build(result: BuildResult) -> None:
        prefix = "Build" if state["first_build"] else "Rebuild"
        state["first_build"] = False
        _print_result(result, prefix=prefix)

    def on_error(exc: AsteriaError) -> None:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)

    def on_change(count: int) -> None:
        print(f"\n{count} change(s) detected, rebuilding...")

    def on_watch_start(watch_paths: list[Path]) -> None:
        watched_names = ", ".join(
            str(p.relative_to(project_root)) if p.is_relative_to(project_root) else str(p)
            for p in watch_paths
        )
        print(f"Watching for changes in: {watched_names} (live reload active)\n")

    dev = DevServer(
        project_root,
        host=host,
        port=port,
        converter_name=converter_name,
        watch=watch,
        on_build=on_build,
        on_error=on_error,
        on_change=on_change,
        on_watch_start=on_watch_start,
    )

    if not dev.start():
        return 1

    print(f"\nServing at {dev.url} (Ctrl+C to exit)")

    if not watch:
        reason = "'watchfiles' is not installed" if watch_missing else "--no-watch"
        print(f"Automatic rebuild and live reload disabled ({reason}).")
        if watch_missing:
            print('Install it with: pip install "asteria[watch]"')
    elif not dev.status().watching:
        print(
            "Nothing to observe (source/content, source/static, "
            "source/site.yaml, theme directory not found)."
        )

    try:
        _idle_until_interrupted()
    finally:
        dev.stop()

    return 0


def _idle_until_interrupted() -> None:
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass