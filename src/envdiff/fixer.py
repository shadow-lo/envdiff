"""Append missing keys to the example file, with empty values.

This module only ever writes key names followed by ``=``. It has no access to
any value from the real env file: callers pass plain key names.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .parser import KEY_RE


@dataclass
class FixPlan:
    path: str
    keys: List[str]
    creates_file: bool

    @property
    def lines(self) -> List[str]:
        return [f"{k}=" for k in self.keys]


def plan(example_path: str, keys: List[str]) -> FixPlan:
    for k in keys:
        if not KEY_RE.fullmatch(k):  # defensive: only bare key names may be written
            raise ValueError("refusing to write an invalid key name")
    return FixPlan(example_path, list(keys), not Path(example_path).exists())


def backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".bak")
    n = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak{n}")
        n += 1
    return candidate


def apply(p: FixPlan) -> Optional[str]:
    """Write the plan. Returns the backup path (None if the file was new)."""
    path = Path(p.path)
    if not p.keys:
        return None
    if p.creates_file:
        path.write_bytes(("\n".join(p.lines) + "\n").encode("utf-8"))
        return None
    backup = backup_path(path)
    shutil.copy2(path, backup)
    data = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    if data and not data.endswith((b"\n", b"\r")):
        data += newline
    data += newline.join(line.encode("utf-8") for line in p.lines) + newline
    path.write_bytes(data)
    return str(backup)
