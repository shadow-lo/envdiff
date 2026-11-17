"""Command-line entry point."""

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .compare import all_missing, compare
from .fixer import apply, plan
from .parser import EnvFile, parse_file
from .report import build, fix_info, render, render_fix
from .scanner import scan

EXIT_OK, EXIT_DIFF, EXIT_ERROR = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="envdiff",
        description="Compare .env files with .env.example by key name. Values are never printed.",
        epilog="With no FILE: compares .env with .env.example. With several FILEs the last one "
               "is the reference (example) unless --example is given.",
    )
    p.add_argument("files", nargs="*", metavar="FILE", help="env files to compare")
    p.add_argument("--example", metavar="PATH", help="reference file (default: .env.example)")
    p.add_argument("--check", action="store_true",
                   help="exit 1 if anything differs, a secret is found (with --scan) or a line cannot be parsed")
    p.add_argument("--scan", action="store_true", help="look for real-looking secrets in the example file")
    p.add_argument("--fix", action="store_true",
                   help="add missing keys to the example file with empty values (preview first)")
    p.add_argument("--dry-run", action="store_true", help="with --fix: only show what would be added")
    p.add_argument("-y", "--yes", action="store_true", help="with --fix: write without asking")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--no-color", action="store_true", help="plain output (NO_COLOR is respected too)")
    p.add_argument("--version", action="version", version=f"envdiff {__version__}")
    return p


def resolve_files(files: List[str], example: Optional[str]):
    files = list(files)
    if example is None:
        example = files.pop() if len(files) >= 2 else ".env.example"
    if not files:
        files = [".env"]
    return files, example


def use_color(args) -> bool:
    if args.no_color or args.json or os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _err(msg: str) -> None:
    print(f"envdiff: {msg}", file=sys.stderr)


def confirm(question: str) -> bool:
    if not (hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
        return False
    print(question + " [y/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = input()
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def run(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if (args.dry_run or args.yes) and not args.fix:
        _err("--dry-run and --yes only work together with --fix")
        return EXIT_ERROR
    env_paths, example_path = resolve_files(args.files, args.example)

    envs = []
    for path in env_paths:
        if not os.path.isfile(path):
            _err(f"file not found: {path}")
            return EXIT_ERROR
        envs.append(parse_file(path))
    if os.path.isfile(example_path):
        example = parse_file(example_path)
    elif args.fix:
        example = EnvFile(path=example_path)
    else:
        _err(f"file not found: {example_path}")
        return EXIT_ERROR

    diffs = [compare(e, example) for e in envs]
    findings = scan(example) if args.scan else None
    color = use_color(args)

    fix = None
    if args.fix:
        fp = plan(example_path, all_missing(diffs))
        written, backup = False, None
        if fp.keys and not args.dry_run:
            if not args.yes and not args.json:
                for line in render_fix(fix_info(fp, False, None), color):
                    print(line, file=sys.stderr)
            if args.yes or (not args.json and confirm("Write these keys? A backup is saved first.")):
                backup = apply(fp)
                written = True
        fix = fix_info(fp, written, backup)

    data = build(example, envs, diffs, findings, fix)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(render(data, color))
        if fix and fix["keys"] and not fix["written"] and not args.dry_run:
            print("Nothing was written. Re-run with --fix --yes to write.")
    if args.check and not data["ok"]:
        return EXIT_DIFF
    return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    try:
        return run(argv)
    except KeyboardInterrupt:
        _err("interrupted")
        return EXIT_ERROR
    except OSError as exc:
        # Only the file name and the OS reason, never file contents.
        name = exc.filename if exc.filename else "file"
        _err(f"cannot access {name}: {exc.strerror or type(exc).__name__}")
        return EXIT_ERROR
    except Exception as exc:  # pragma: no cover - last-resort guard
        # Deliberately no message and no traceback: they could echo data.
        _err(f"unexpected error ({type(exc).__name__})")
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
