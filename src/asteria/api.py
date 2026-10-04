"""
Public, frontend-agnostic API for Asteria.

Everything a UI needs -- the CLI, a GTK4 app, a test, a one-off script --
lives here as plain functions and classes that:

  * take/return real Python objects (Path, dataclasses, structured
    results), never text meant for a terminal;
  * never print anything and never call sys.exit();
  * never block on terminal input (no input() prompts -- a caller that
    needs a confirmation step, like the CLI's `asteria reset-theme`
    prompt, does that itself *before* calling in here);
  * report failures as exceptions (AsteriaError) or, for the long-running
    dev server, as callbacks -- never as a process exit code.

`cli.py` is a thin wrapper around this module: every command it exposes
just calls one of these functions and formats the result for a
terminal. Any other frontend (a GTK4 app, a script, a test) should
import straight from here instead of going through the CLI or shelling
out to `asteria ...` as a subprocess.

Threading note for GUI frontends: build_project/check_project/
clean_project/etc. are synchronous and do file I/O, so a GUI should
normally call them from a worker thread rather than its main/UI thread.
DevServer (see server.py) already runs its own work in background
threads and reports back through callbacks -- see its docstring for the
main-thread-marshalling caveat that applies to those callbacks.

File watching: DevServer's built-in watcher needs the optional
`watchfiles` package (`pip install "asteria[watch]"`); check
`watch_backend_available()` to know whether it's there. A frontend
with its own watcher (e.g. Gio.FileMonitor in a GTK app) doesn't need
it: create `DevServer(..., watch=False, live_reload=True)`, watch the
paths returned by `discover_watch_paths()`, and call
`DevServer.rebuild()` (from a worker thread) when something changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .build import BuildResult, run_build
from .cache import clear_cache
from .config import SiteConfig, load_config
from .config import reset_theme as _reset_bundled_theme
from .errors import AsteriaError
from .scaffold import create_project
from .server import (
    DevServer,
    DevServerStatus,
    discover_watch_paths,
    watch_backend_available,
)
from .writer import clean_output

__all__ = [
    "AsteriaError",
    "BuildResult",
    "SiteConfig",
    "CleanResult",
    "DevServer",
    "DevServerStatus",
    "build_project",
    "check_project",
    "clean_project",
    "clear_project_cache",
    "create_new_project",
    "discover_watch_paths",
    "load_project_config",
    "reset_project_theme",
    "watch_backend_available",
]


def load_project_config(project_root: Path, config_filename: str = "site.yaml") -> SiteConfig:
    """Loads and returns a project's parsed `site.yaml` (merged with the
    built-in defaults), without running a build. Useful for a UI that
    wants to show the site title, output directory, theme in use, etc.
    as soon as a project is opened, before the user asks for a build.

    Raises AsteriaError if the file is missing or not valid YAML.
    """
    return load_config(project_root / "source" / config_filename)


def build_project(
    project_root: Path,
    converter_name: str = "odt2web",
    config_filename: str = "site.yaml",
) -> BuildResult:
    """Runs a full build and writes the output to disk.

    Raises AsteriaError on fatal, whole-project errors (bad site.yaml,
    missing theme, ...). Content-level problems (a broken reference, a
    missing translation, ...) do NOT raise -- they're collected in
    `result.diagnostics` instead. Always check `result.success` (or
    `result.diagnostics.has_errors`) after a call that didn't raise.
    """
    return run_build(project_root, config_filename=config_filename, converter_name=converter_name)


def check_project(
    project_root: Path,
    converter_name: str = "auto",
    config_filename: str = "site.yaml",
) -> BuildResult:
    """Validates the project (YAML, ODT files, ids, references) without
    writing anything to disk -- same as `build_project`, but with
    `dry_run=True`. `result.generated_files` is always empty here; use
    `result.pages` / `result.posts` / `result.diagnostics` instead.
    """
    return run_build(
        project_root,
        config_filename=config_filename,
        converter_name=converter_name,
        dry_run=True,
    )


@dataclass
class CleanResult:
    """What `clean_project` actually did, so a UI can report it without
    re-deriving it from a SiteConfig itself."""

    output_dir: Path
    output_removed: bool
    cache_removed: bool


def clean_project(
    project_root: Path,
    remove_cache: bool = False,
    config_filename: str = "site.yaml",
) -> CleanResult:
    """Removes the generated site (`config.output_dir`) and, optionally,
    the incremental conversion cache.

    Raises AsteriaError if site.yaml itself can't be read -- it's needed
    to know where the output directory even is.
    """
    config = load_config(project_root / "source" / config_filename)
    output_removed = config.output_dir.exists()
    clean_output(config)
    cache_removed = remove_cache and clear_cache(project_root)
    return CleanResult(
        output_dir=config.output_dir,
        output_removed=output_removed,
        cache_removed=cache_removed,
    )


def clear_project_cache(project_root: Path) -> bool:
    """Removes just the incremental conversion cache
    (`.asteria-cache.json`), leaving any already-generated output in
    place. Returns whether a cache file actually existed to remove."""
    return clear_cache(project_root)


def create_new_project(target_dir: Path) -> list[str]:
    """Scaffolds a new Asteria project at `target_dir` (created if it
    doesn't exist yet).

    Raises AsteriaError if the directory already exists and isn't empty.
    Returns the created files' paths, relative to `target_dir`.
    """
    return create_project(target_dir)


def reset_project_theme(project_root: Path) -> Path:
    """Overwrites `source/themes/minimal` with Asteria's bundled
    'minimal' theme, discarding any local edits to it.

    Unlike the CLI's `reset-theme` command, this never prompts for
    confirmation -- a UI that wants one (e.g. a GTK confirmation dialog)
    should ask the user itself before calling this. Raises AsteriaError
    if the bundled theme is missing (a broken installation).
    """
    return _reset_bundled_theme(project_root)