"""Parse .env files.

Security rule: nothing in this module ever puts a *value* (or a raw line) into
an exception message, an issue, or a repr. Issues carry only a line number,
a key name when one is known, and a fixed message.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")
EXPORT_RE = re.compile(r"export\s+")
DOUBLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "$": "$"}


@dataclass
class Entry:
    key: str
    line: int
    # repr=False: a value must never show up in a debug print or a traceback.
    value: str = field(repr=False, default="")


@dataclass
class Issue:
    line: int
    message: str
    key: Optional[str] = None


@dataclass
class EnvFile:
    path: str
    entries: List[Entry] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)

    @property
    def keys(self) -> List[str]:
        """Unique keys in first-seen order."""
        seen: Dict[str, None] = {}
        for e in self.entries:
            seen.setdefault(e.key, None)
        return list(seen)

    def last(self) -> Dict[str, Entry]:
        """Key -> the entry that wins (the last definition)."""
        out: Dict[str, Entry] = {}
        for e in self.entries:
            out[e.key] = e
        return out


def _read_quoted(lines: List[str], i: int, start: int, quote: str) -> Tuple[Optional[str], int, int]:
    """Read a quoted value that starts at lines[i][start] (the opening quote).

    Returns (value, last_line_index, index_after_closing_quote) or
    (None, i, 0) if the quote is never closed.
    """
    buf: List[str] = []
    row, col = i, start + 1
    while row < len(lines):
        text = lines[row]
        while col < len(text):
            ch = text[col]
            if quote == '"' and ch == "\\" and col + 1 < len(text):
                nxt = text[col + 1]
                buf.append(DOUBLE_ESCAPES.get(nxt, "\\" + nxt))
                col += 2
                continue
            if ch == quote:
                return "".join(buf), row, col + 1
            buf.append(ch)
            col += 1
        buf.append("\n")
        row, col = row + 1, 0
    return None, i, 0


def _skip_ws(line: str, pos: int) -> int:
    while pos < len(line) and line[pos] in " \t":
        pos += 1
    return pos


def parse_text(text: str, path: str = "<string>") -> EnvFile:
    env = EnvFile(path=path)
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        lineno = i + 1
        line = lines[i]
        pos = len(line) - len(line.lstrip())
        if pos == len(line) or line[pos] == "#":
            i += 1
            continue
        m = EXPORT_RE.match(line, pos)
        if m:
            pos = m.end()
        km = KEY_RE.match(line, pos)
        if not km:
            env.issues.append(Issue(lineno, "invalid line: expected KEY=VALUE"))
            i += 1
            continue
        key = km.group(0)
        pos = _skip_ws(line, km.end())
        if pos >= len(line) or line[pos] != "=":
            env.issues.append(Issue(lineno, "invalid line: missing '='"))
            i += 1
            continue
        pos = _skip_ws(line, pos + 1)
        if pos < len(line) and line[pos] in ('"', "'", "`"):
            value, end_row, _ = _read_quoted(lines, i, pos, line[pos])
            if value is None:
                env.issues.append(Issue(lineno, "unterminated quoted value", key))
                i += 1
                continue
            env.entries.append(Entry(key, lineno, value))
            i = end_row + 1
            continue
        rest = line[pos:]
        # Unquoted: an inline comment starts at whitespace followed by '#'.
        if rest.startswith("#"):
            value = ""
        else:
            cut = re.search(r"\s#", rest)
            value = (rest[:cut.start()] if cut else rest).rstrip()
        env.entries.append(Entry(key, lineno, value))
        i += 1
    _flag_duplicates(env)
    return env


def _flag_duplicates(env: EnvFile) -> None:
    first: Dict[str, int] = {}
    for e in env.entries:
        if e.key in first:
            env.issues.append(Issue(e.line, f"duplicate key (first defined on line {first[e.key]})", e.key))
        else:
            first[e.key] = e.line


def read_text(path: Union[str, Path]) -> str:
    data = Path(path).read_bytes()
    # utf-8-sig drops a BOM; replace keeps going on odd bytes. Values are never printed.
    return data.decode("utf-8-sig", errors="replace")


def parse_file(path: Union[str, Path]) -> EnvFile:
    return parse_text(read_text(path), str(path))
