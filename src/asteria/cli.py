"""
Asteria CLI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import (
    build_project,
    check_project,
    clean_project,
    create_new_project,
    reset_project_theme,
)
from .errors import AsteriaError
from .server import serve as run_serve


def _cmd_build(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    try:
        result = build_project(project_root, converter_name=args.converter)
    except AsteriaError as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        return 1

    for diag in result.diagnostics:
        print(diag)

    if not result.success:
        print(
            f"\nBuild failed: {len(result.diagnostics.errors)} error(s), "
            f"{len(result.diagnostics.warnings)} warning(s).",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nBuild complete: {len(result.pages)} page(s), {len(result.posts)} post(s), "
        f"{len(result.generated_files)} generated file(s), "
        f"{len(result.diagnostics.warnings)} warning(s) -> {result.output_dir}"
    )
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    try:
        result = clean_project(project_root, remove_cache=args.cache)
    except AsteriaError as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Output directory removed: {result.output_dir}")
    if args.cache:
        if result.cache_removed:
            print("Incremental conversion cache removed.")
        else:
            print("There was no conversion cache to remove.")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    return run_serve(
        project_root,
        host=args.host,
        port=args.port,
        converter_name=args.converter,
        watch=not args.no_watch,
    )


def _cmd_check(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()
    try:
        result = check_project(project_root, converter_name=args.converter)
    except AsteriaError as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        return 1

    for diag in result.diagnostics:
        print(diag)

    if not result.success:
        print(
            f"\nValidation failed: {len(result.diagnostics.errors)} error(s), "
            f"{len(result.diagnostics.warnings)} warning(s).",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nValidation ok: {len(result.pages)} page(s), {len(result.posts)} post(s), "
        f"{len(result.diagnostics.warnings)} warning(s). No file was written "
        "(use 'asteria build' to generate the site)."
    )
    return 0


def _cmd_reset_theme(args: argparse.Namespace) -> int:
    project_root = Path(args.project).resolve()

    if not args.yes:
        answer = input(
            "This overwrites any local edits to source/themes/minimal "
            "with the bundled theme. Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted; nothing was changed.")
            return 1

    try:
        destination = reset_project_theme(project_root)
    except AsteriaError as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Bundled theme restored to {destination}")
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    target_dir = Path(args.path).resolve()
    try:
        created = create_new_project(target_dir)
    except AsteriaError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Project created in {target_dir}\n")
    for relative in created:
        print(f"  {relative}")
    print(
        f"\nNext steps:\n  cd {args.path}\n  asteria serve\n"
        "\nThe initial page (content/pages/welcome.odt) explains the basic"
        
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asteria", description="ODT-based SSG")
    parser.add_argument(
        "--project",
        default=".",
        help="Project root directory (where site.yaml is located). Default: current directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    converter_choices = ["auto", "odt2web"]
    converter_help = "ODT→HTML converter to use. 'auto' and 'odt2web' are equivalent today."

    build_p = subparsers.add_parser("build", help="Generate the site")
    build_p.add_argument("--converter", default="odt2web", choices=converter_choices, help=converter_help)
    build_p.set_defaults(func=_cmd_build)

    clean_p = subparsers.add_parser("clean", help="Removes the generated files")
    clean_p.add_argument(
        "--cache",
        action="store_true",
        help="It also removes the incremental conversion cache (.asteria-cache.json).",
    )
    clean_p.set_defaults(func=_cmd_clean)

    serve_p = subparsers.add_parser("serve", help="Generates the site and serves it locally.")
    serve_p.add_argument("--host", default="127.0.0.1", help="Address to serve on. Default: 127.0.0.1.")
    serve_p.add_argument("--port", type=int, default=8000, help="Service port. Standard: 8000.")
    serve_p.add_argument("--converter", default="auto", choices=converter_choices, help=converter_help)
    serve_p.add_argument(
        "--no-watch",
        action="store_true",
        help="Do not watch for changes in content/static/theme/site.yaml (no automatic rebuild). "
        "Watching needs the optional 'watchfiles' package: pip install \"asteria[watch]\".",
    )
    serve_p.set_defaults(func=_cmd_serve)

    check_p = subparsers.add_parser(
        "check", help="Validates the project (YAML, ODT, IDs, references) without generating the site."
    )
    check_p.add_argument("--converter", default="auto", choices=converter_choices, help=converter_help)
    check_p.set_defaults(func=_cmd_check)

    reset_theme_p = subparsers.add_parser(
        "reset-theme",
        help="Restores the bundled 'minimal' theme (source/themes/minimal), "
        "overwriting local edits to it.",
    )
    reset_theme_p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt (for non-interactive use).",
    )
    reset_theme_p.set_defaults(func=_cmd_reset_theme)

    new_p = subparsers.add_parser("new", help="Create a new Asteria project")
    new_p.add_argument(
        "path",
        nargs="?",
        default="my-site",
        help="Directory where the project will be created (created if it does not exist). "
        "Default: 'my-site' in the current directory.",
    )
    new_p.set_defaults(func=_cmd_new)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())