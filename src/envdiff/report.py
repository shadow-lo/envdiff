"""Build and render results. Only key names, line numbers and masks are used here."""

from dataclasses import asdict
from typing import List, Optional

from .compare import Diff
from .fixer import FixPlan
from .parser import EnvFile
from .scanner import Finding

GREEN, RED, YELLOW, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"


def build(example: EnvFile, envs: List[EnvFile], diffs: List[Diff],
          findings: Optional[List[Finding]], fix: Optional[dict] = None) -> dict:
    warnings = []
    for f in envs + [example]:
        for issue in f.issues:
            warnings.append({"file": f.path, "line": issue.line, "key": issue.key,
                             "message": issue.message})
    missing = sum(len(d.missing) for d in diffs)
    extra = sum(len(d.extra) for d in diffs)
    data = {
        "reference": example.path,
        "files": [
            {"path": d.path, "missing": d.missing, "extra": d.extra,
             "common_count": len(d.common), "in_sync": d.clean}
            for d in diffs
        ],
        "scan": None if findings is None else {
            "path": example.path,
            "findings": [asdict(f) for f in findings],
        },
        "parse_warnings": warnings,
        "summary": {
            "missing": missing,
            "extra": extra,
            "secrets": len(findings or []),
            "parse_warnings": len(warnings),
        },
    }
    data["ok"] = not (missing or extra or findings or warnings)
    if fix is not None:
        data["fix"] = fix
    return data


def fix_info(p: FixPlan, written: bool, backup: Optional[str]) -> dict:
    return {"path": p.path, "keys": p.keys, "creates_file": p.creates_file,
            "written": written, "backup": backup}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def render(data: dict, color: bool = False) -> str:
    def c(code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if color else text

    ref = data["reference"]
    out: List[str] = []
    for f in data["files"]:
        out.append(c(BOLD, f"Comparing: {f['path']}  <->  {ref}"))
        if f["in_sync"]:
            out.append(c(GREEN, f"  ✓ in sync ({_plural(f['common_count'], 'key')})"))
        if f["missing"]:
            out.append(f"\nMissing from {ref}:")
            out.extend(c(GREEN, f"  + {k}") for k in f["missing"])
        if f["extra"]:
            out.append(f"\nExtra (not in {f['path']}):")
            out.extend(c(RED, f"  - {k}") for k in f["extra"])
        out.append("")

    scan = data["scan"]
    if scan is not None:
        if scan["findings"]:
            out.append(c(YELLOW, f"Warning: {scan['path']} may contain real secrets"))
            width = max(len(x["key"]) for x in scan["findings"])
            mwidth = max(len(x["masked"]) for x in scan["findings"])
            for x in scan["findings"]:
                out.append(c(YELLOW, f"  ! line {x['line']:<3} {x['key']:<{width}}  ")
                           + f"{x['masked']:<{mwidth}}  {x['reason']} ({x['severity']})")
            out.append(c(DIM, "  Values are masked. Rotate any real key that was committed."))
        else:
            out.append(c(GREEN, f"Scan: no likely secrets in {scan['path']}"))
        out.append("")

    if data["parse_warnings"]:
        out.append(c(YELLOW, "Parse warnings:"))
        for w in data["parse_warnings"]:
            key = f" ({w['key']})" if w["key"] else ""
            out.append(f"  {w['file']} line {w['line']}: {w['message']}{key}")
        out.append("")

    fix = data.get("fix")
    if fix is not None:
        out.extend(render_fix(fix, color))
        out.append("")

    s = data["summary"]
    parts = [_plural(s["missing"], "missing key"), _plural(s["extra"], "extra key")]
    if scan is not None:
        parts.append(_plural(s["secrets"], "possible secret"))
    if s["parse_warnings"]:
        parts.append(_plural(s["parse_warnings"], "parse warning"))
    out.append(c(GREEN if data["ok"] else BOLD, "Result: " + ", ".join(parts)))
    return "\n".join(out)


def render_fix(fix: dict, color: bool = False) -> List[str]:
    def c(code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if color else text

    if not fix["keys"]:
        return [f"Fix: nothing to add to {fix['path']}"]
    verb = "Created" if fix["creates_file"] else "Appended to"
    if fix["written"]:
        head = f"Fix: {verb} {fix['path']} ({_plural(len(fix['keys']), 'key')}, empty values)"
    else:
        action = "create" if fix["creates_file"] else "append to"
        head = f"Fix preview: would {action} {fix['path']} (empty values, nothing written yet)"
    lines = [c(BOLD, head)]
    lines.extend(c(GREEN, f"  + {k}=") for k in fix["keys"])
    if fix["backup"]:
        lines.append(c(DIM, f"  backup: {fix['backup']}"))
    return lines
