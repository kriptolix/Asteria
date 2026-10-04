"""
New project scaffold (`asteria new`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .errors import AsteriaError

def create_project(target_dir: Path) -> list[str]:

    if target_dir.exists() and any(target_dir.iterdir()):
            raise AsteriaError(
                f"'{target_dir}' It already exists and is not empty, choose another "
                "directory or empty it before running 'asteria new'."
            )

    target_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    base_source = Path(__file__).parent / "site" / "source"
    edit_source = target_dir / "source"

    shutil.copytree(base_source, edit_source)

    for path in sorted(edit_source.rglob("*")):
            if path.is_file():
                created.append(str(path.relative_to(target_dir)))
    
    return created