"""
Recursive Gio.FileMonitor watcher for an Asteria project.

This module belongs to the GTK application, NOT to the asteria library:
the library must stay free of GLib/GTK imports so `pip install asteria`
works everywhere. It replaces the library's optional `watchfiles`-based
watcher: on every (debounced) change it calls `DevServer.rebuild()` in a
worker thread and reports the outcome back on the GLib main loop.

Everything public here must be used from the GLib main thread: the
Gio monitors deliver their signals in the main context they were
created in, and the callbacks below are invoked from it.

Typical wiring (`DevServer.start()` blocks during the initial build, so
it runs in a worker thread; the watcher is created afterwards, back on
the main thread):

    def start_server(self):                         # main thread
        self.dev = DevServer(
            root, watch=False, live_reload=True,
            on_build=..., on_error=...,             # these run in worker threads:
        )                                           # marshal with GLib.idle_add
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self):                        # worker thread
        ok = self.dev.start()
        GLib.idle_add(self._server_started, ok)

    def _server_started(self, ok):                  # main thread
        if ok:
            self.watcher = ProjectWatcher(root, self.dev, on_rebuilt=self._on_rebuilt)
            self.watcher.start()
        return GLib.SOURCE_REMOVE

    def close(self):                                # main thread
        self.watcher.stop()
        self.dev.stop()
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path

from gi.repository import Gio, GLib

from asteria.api import BuildResult, DevServer, discover_watch_paths

log = logging.getLogger(__name__)

# Events that mean "something under this directory may have changed".
# CHANGED is included on purpose: it fires repeatedly while a file is
# being written, and each one simply pushes the debounce timer back, so a
# rebuild only starts once writing has settled.
_RELEVANT_EVENTS = frozenset(
    {
        Gio.FileMonitorEvent.CHANGED,
        Gio.FileMonitorEvent.CHANGES_DONE_HINT,
        Gio.FileMonitorEvent.CREATED,
        Gio.FileMonitorEvent.DELETED,
        Gio.FileMonitorEvent.MOVED_IN,
        Gio.FileMonitorEvent.MOVED_OUT,
        Gio.FileMonitorEvent.RENAMED,
    }
)

# Editor/office leftovers that must not trigger a rebuild (LibreOffice
# writes ".~lock.<name>#" next to every open document).
_IGNORED_PREFIXES = (".~lock.", ".#")
_IGNORED_SUFFIXES = ("~", ".swp", ".swx", ".tmp")
_IGNORED_DIRS = frozenset({".git", ".hg", ".svn", "__pycache__"})


def _is_ignored(path: Path) -> bool:
    if any(part in _IGNORED_DIRS for part in path.parts):
        return True
    name = path.name
    return name.startswith(_IGNORED_PREFIXES) or name.endswith(_IGNORED_SUFFIXES)


class ProjectWatcher:
    """Watches a project's editable files and rebuilds through a DevServer.

    `dev` must already be started (or at least constructed) with
    `watch=False, live_reload=True`, so the built-in `watchfiles` watcher
    stays off while pages still get the live-reload script.

    Callbacks (all invoked on the GLib main thread):

        on_rebuild_started()
            A rebuild is about to run in the worker thread.
        on_rebuilt(result, error)
            The rebuild finished. `result` is the BuildResult, or None
            if the build failed fatally (bad site.yaml, missing theme...)
            -- in that case the DevServer's own `on_error` callback has
            already been called with the AsteriaError, and `error` is
            None. `error` is only set for an unexpected exception.
        on_error(message)
            A directory couldn't be monitored (for instance the inotify
            watch limit was reached). Watching continues for the rest.
    """

    def __init__(
        self,
        project_root: Path,
        dev: DevServer,
        on_rebuilt: Callable[[BuildResult | None, Exception | None], None] | None = None,
        on_rebuild_started: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        debounce_ms: int = 300,
    ) -> None:
        self._root = project_root
        self._dev = dev
        self._on_rebuilt = on_rebuilt
        self._on_rebuild_started = on_rebuild_started
        self._on_error = on_error
        self._debounce_ms = debounce_ms

        self._started = False
        self._roots: tuple[Path, ...] = ()
        self._monitors: dict[Path, Gio.FileMonitor] = {}
        # Directories monitored as part of a recursive tree: every event
        # in them counts.
        self._tree_dirs: set[Path] = set()
        # Every root (file or directory) is also watched through its
        # parent directory, non-recursively, reacting only to the listed
        # names:
        #   * a root *file* (site.yaml): watching the parent keeps working
        #     when editors save atomically (write a temp file, then rename
        #     over the original), which would orphan a per-file monitor;
        #   * a root *directory* (content/, static/, the theme): its own
        #     monitor is bound to the directory's inode and dies with it,
        #     so only the parent can notice it being recreated.
        self._only_names: dict[Path, set[str]] = {}

        self._timer_id = 0
        self._building = False
        self._dirty = False  # changes arrived while a build was running

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        """Starts monitoring. Call from the GLib main thread."""
        if self._started:
            return
        self._started = True
        # existing_only=False: keep tracking roots that are missing right
        # now, so they're picked up when (re)created.
        self._roots = tuple(discover_watch_paths(self._root, existing_only=False))
        self._add_roots(self._roots)

    def stop(self) -> None:
        """Stops monitoring and cancels any pending rebuild. A build that
        is already running finishes, but its result is discarded."""
        self._started = False
        self._dirty = False
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0
        self._teardown_monitors()

    # ----------------------------------------------------- monitor management

    def _add_roots(self, roots: tuple[Path, ...]) -> None:
        for root in roots:
            if root.is_dir():
                self._add_tree(root)
            # A root that doesn't exist yet can still be picked up through
            # its parent -- provided the parent itself exists.
            if root.parent.is_dir():
                self._add_via_parent(root)

    def _add_tree(self, root: Path) -> None:
        # Gio.FileMonitor is not recursive: one monitor per directory.
        for dirpath, dirnames, _files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS]
            self._add_dir(Path(dirpath), tree=True)

    def _add_via_parent(self, path: Path) -> None:
        self._only_names.setdefault(path.parent, set()).add(path.name)
        self._add_dir(path.parent, tree=False)

    def _add_dir(self, directory: Path, tree: bool) -> None:
        if tree:
            self._tree_dirs.add(directory)
        if directory in self._monitors:
            return
        try:
            monitor = Gio.File.new_for_path(str(directory)).monitor_directory(
                Gio.FileMonitorFlags.NONE, None
            )
        except GLib.Error as exc:
            self._tree_dirs.discard(directory)
            self._report(f"Cannot watch {directory}: {exc.message}")
            return
        monitor.connect("changed", self._on_changed, directory)
        self._monitors[directory] = monitor

    def _drop_tree(self, root: Path) -> None:
        """Cancels the monitors of `root` and everything below it (the
        directory was deleted or moved away)."""
        for directory in list(self._monitors):
            if directory == root or root in directory.parents:
                self._monitors.pop(directory).cancel()
                self._tree_dirs.discard(directory)

    def _teardown_monitors(self) -> None:
        for monitor in self._monitors.values():
            monitor.cancel()
        self._monitors.clear()
        self._tree_dirs.clear()
        self._only_names.clear()

    def _sync_roots(self) -> None:
        """Re-reads what should be watched. The set can change after a
        rebuild -- editing site.yaml may switch the active theme -- so
        monitors are recreated when it does. Changes that happen in the
        instant between the two steps are not lost in practice: this runs
        on the main thread right after a rebuild that already picked up
        the new configuration."""
        wanted = tuple(discover_watch_paths(self._root, existing_only=False))
        if wanted != self._roots:
            self._teardown_monitors()
            self._roots = wanted
            self._add_roots(wanted)

    # ------------------------------------------------------- event handling

    def _on_changed(self, _monitor, file, _other, event, directory: Path) -> None:
        if event not in _RELEVANT_EVENTS:
            return
        raw_path = file.get_path()
        if raw_path is None:  # not a local path
            return
        path = Path(raw_path)
        if _is_ignored(path):
            return

        in_tree = directory in self._tree_dirs
        if not in_tree:
            only = self._only_names.get(directory)
            if only is not None and path.name not in only:
                return

        if in_tree:
            if event in (Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.MOVED_IN):
                if path.is_dir():
                    self._add_tree(path)  # new sub-directory: watch it too
            elif event in (Gio.FileMonitorEvent.DELETED, Gio.FileMonitorEvent.MOVED_OUT):
                if path in self._monitors:
                    self._drop_tree(path)
        elif path in self._roots:
            # A root reported by its parent's monitor. If it is a
            # directory that was deleted/moved away and later recreated,
            # its old monitor is dead or stale: replace it.
            if event in (Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.MOVED_IN):
                if path.is_dir():
                    self._drop_tree(path)
                    self._add_tree(path)
            elif event in (Gio.FileMonitorEvent.DELETED, Gio.FileMonitorEvent.MOVED_OUT):
                self._drop_tree(path)

        self._schedule_rebuild()

    def _schedule_rebuild(self) -> None:
        # Debounce: editors and LibreOffice emit bursts of events per
        # save, so wait until things go quiet before building.
        if self._timer_id:
            GLib.source_remove(self._timer_id)
        self._timer_id = GLib.timeout_add(self._debounce_ms, self._on_debounce_elapsed)

    def _on_debounce_elapsed(self) -> bool:
        self._timer_id = 0
        if self._building:
            self._dirty = True  # rebuild again as soon as this build ends
        else:
            self._start_build()
        return GLib.SOURCE_REMOVE

    # -------------------------------------------------------------- building

    def _start_build(self) -> None:
        self._building = True
        if self._on_rebuild_started:
            self._on_rebuild_started()
        threading.Thread(target=self._build_worker, name="asteria-rebuild", daemon=True).start()

    def _build_worker(self) -> None:
        # Worker thread: never touch GTK/GLib objects here except idle_add.
        result: BuildResult | None = None
        error: Exception | None = None
        try:
            result = self._dev.rebuild()
        except Exception as exc:  # noqa: BLE001 - must never leave the watcher stuck
            error = exc
        GLib.idle_add(self._finish_build, result, error)

    def _finish_build(self, result: BuildResult | None, error: Exception | None) -> bool:
        self._building = False
        if not self._started:  # stop() was called while building
            return GLib.SOURCE_REMOVE

        if self._on_rebuilt:
            self._on_rebuilt(result, error)
        self._sync_roots()

        if self._dirty:
            self._dirty = False
            self._start_build()
        return GLib.SOURCE_REMOVE

    def _report(self, message: str) -> None:
        log.warning(message)
        if self._on_error:
            self._on_error(message)