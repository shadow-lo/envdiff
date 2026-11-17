import io
import json
import subprocess
import sys

import pytest

from envdiff import cli


@pytest.fixture
def project(tmp_path, monkeypatch, write, fake_secrets):
    """.env holds every fake secret; .env.example leaks some of them."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    env_lines = [f"{k}={v}" for k, v in fake_secrets.items()] + [
        'MULTI="line one', 'line two"', "export PORT=8080"]
    write(".env", "\n".join(env_lines) + "\n")
    write(".env.example", "\n".join([
        "# example",
        f"OPENAI_API_KEY={fake_secrets['OPENAI_API_KEY']}",
        f"GITHUB_TOKEN={fake_secrets['GITHUB_TOKEN']}",
        "PORT=",
        "API_KEY=your-key-here",
        "LEGACY_URL=",
        'BROKEN="never closed',
    ]) + "\n")
    return tmp_path


def run(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def assert_no_values(text, fake_secrets):
    for value in fake_secrets.values():
        assert value not in text
        # Not even a long chunk of it.
        assert value[4:16] not in text
    assert "line one" not in text and "line two" not in text


ALL_MODES = [
    [], ["--scan"], ["--check"], ["--scan", "--check"], ["--json"], ["--scan", "--json"],
    ["--fix", "--dry-run"], ["--fix", "--dry-run", "--json"], ["--fix", "--yes", "--scan"],
    ["--fix", "--yes", "--json", "--scan"], [".env", ".env.example", "--scan"],
]


@pytest.mark.parametrize("args", ALL_MODES)
def test_no_value_ever_printed(project, capsys, fake_secrets, args):
    code, out, err = run(capsys, *args)
    assert code in (0, 1)
    assert_no_values(out + err, fake_secrets)


def test_fixed_file_contains_no_new_values(project, capsys, fake_secrets):
    before = (project / ".env.example").read_text(encoding="utf-8")
    run(capsys, "--fix", "--yes")
    added = (project / ".env.example").read_text(encoding="utf-8")[len(before):]
    assert added.strip()
    assert all(line.endswith("=") for line in added.splitlines())
    assert_no_values(added, fake_secrets)
    assert (project / ".env.example.bak").read_text(encoding="utf-8") == before


def test_default_output(project, capsys):
    code, out, _ = run(capsys, "--no-color")
    assert code == 0
    assert "Comparing: .env  <->  .env.example" in out
    assert "  + ANTHROPIC_API_KEY" in out and "  + MULTI" in out
    assert "  - LEGACY_URL" in out and "  - API_KEY" in out
    assert ".env.example line 7: unterminated quoted value (BROKEN)" in out
    assert "\033[" not in out
    assert "Scan" not in out


def test_scan_output(project, capsys):
    _, out, _ = run(capsys, "--scan")
    assert "line 2" in out and "sk-****" in out
    assert "line 3" in out and "gh*_****" in out
    assert "2 possible secrets" in out


def test_check_exit_codes(project, capsys, write):
    assert run(capsys, "--check")[0] == 1
    write("a.env", "A=1\nB=2\n")
    write("b.env", "B=\nA=\n")
    code, out, _ = run(capsys, "a.env", "b.env", "--check")
    assert code == 0 and "in sync (2 keys)" in out
    # A secret alone fails --check --scan.
    write("c.env", "TOKEN=" + "gh" + "p_" + "Qz8vR2mK9tLw4XpB7nYc3HdJ6sFg1234\n")
    assert run(capsys, "c.env", "c.env", "--check")[0] == 0
    assert run(capsys, "c.env", "c.env", "--check", "--scan")[0] == 1


def test_json_shape(project, capsys):
    code, out, _ = run(capsys, "--json", "--scan")
    data = json.loads(out)
    assert data["reference"] == ".env.example"
    assert data["ok"] is False
    assert data["summary"]["secrets"] == 2
    f = data["files"][0]
    assert "MULTI" in f["missing"] and "LEGACY_URL" in f["extra"]
    assert {x["masked"] for x in data["scan"]["findings"]} == {"sk-****", "gh*_****"}
    assert "\033[" not in out


def test_multiple_env_files(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    write(".env.development", "A=1\nDEV_ONLY=1\n")
    write(".env.production", "A=1\nPROD_ONLY=1\n")
    write("ref.env", "A=\n")
    code, out, _ = run(capsys, ".env.development", ".env.production", "--example", "ref.env", "--json")
    data = json.loads(out)
    assert [f["missing"] for f in data["files"]] == [["DEV_ONLY"], ["PROD_ONLY"]]
    code, out, _ = run(capsys, ".env.development", ".env.production", "ref.env", "--fix", "--yes")
    assert (tmp_path / "ref.env").read_text(encoding="utf-8") == "A=\nDEV_ONLY=\nPROD_ONLY=\n"
    assert "Appended to ref.env (2 keys, empty values)" in out


def test_single_file_argument_uses_default_example(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    write(".env.production", "A=1\n")
    write(".env.example", "A=\n")
    code, out, _ = run(capsys, ".env.production")
    assert code == 0 and "Comparing: .env.production" in out


def test_fix_preview_without_tty_writes_nothing(project, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    before = (project / ".env.example").read_bytes()
    code, out, err = run(capsys, "--fix")
    assert code == 0
    assert (project / ".env.example").read_bytes() == before
    assert "Fix preview: would append to .env.example" in out
    assert "Re-run with --fix --yes" in out
    assert not (project / ".env.example.bak").exists()


def test_fix_dry_run(project, capsys):
    before = (project / ".env.example").read_bytes()
    code, out, _ = run(capsys, "--fix", "--dry-run")
    assert (project / ".env.example").read_bytes() == before
    assert "Re-run" not in out and "  + MULTI=" in out


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize("answer,written", [("y\n", True), ("n\n", False), ("", False)])
def test_fix_interactive_confirm(project, capsys, monkeypatch, answer, written):
    monkeypatch.setattr(sys, "stdin", FakeTTY(answer))
    before = (project / ".env.example").read_bytes()
    code, out, err = run(capsys, "--fix")
    assert "Write these keys?" in err
    assert ((project / ".env.example").read_bytes() != before) is written


def test_fix_creates_example_when_missing(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    write(".env", "A=1\n")
    code, out, _ = run(capsys, "--fix", "--yes")
    assert code == 0 and "Created .env.example" in out
    assert (tmp_path / ".env.example").read_text(encoding="utf-8") == "A=\n"


def test_fix_nothing_to_add(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    write(".env", "A=1\n")
    write(".env.example", "A=\n")
    code, out, _ = run(capsys, "--fix")
    assert code == 0 and "Fix: nothing to add" in out


def test_errors(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    code, _, err = run(capsys)
    assert code == 2 and "file not found: .env" in err
    write(".env", "A=1\n")
    code, _, err = run(capsys)
    assert code == 2 and "file not found: .env.example" in err
    code, _, err = run(capsys, "--dry-run")
    assert code == 2 and "only work together with --fix" in err


def test_unreadable_reference_is_reported_without_content(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    write(".env", "A=1\n")
    (tmp_path / ".env.example").mkdir()
    code, _, err = run(capsys, "--fix", "--yes")
    assert code == 2 and "envdiff:" in err


def test_color_and_no_color_env(project, capsys, monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    args = cli.build_parser().parse_args([])
    assert cli.use_color(args)
    monkeypatch.setenv("NO_COLOR", "1")
    assert not cli.use_color(args)


def test_colored_render(project, capsys):
    from envdiff import report
    from envdiff.parser import parse_file
    from envdiff.compare import compare
    from envdiff.scanner import scan
    ex = parse_file(".env.example")
    env = parse_file(".env")
    data = report.build(ex, [env], [compare(env, ex)], scan(ex))
    text = report.render(data, color=True)
    assert "\033[32m" in text and "\033[33m" in text


def test_clean_scan_message(tmp_path, monkeypatch, capsys, write):
    monkeypatch.chdir(tmp_path)
    write(".env", "A=1\n")
    write(".env.example", "A=\n")
    code, out, _ = run(capsys, "--scan", "--check")
    assert code == 0 and "Scan: no likely secrets" in out


def test_keyboard_interrupt(monkeypatch, capsys):
    def boom(argv):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "run", boom)
    assert cli.main([]) == 2


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "envdiff 0.1.0" in capsys.readouterr().out


def test_module_entry_point(project):
    proc = subprocess.run([sys.executable, "-m", "envdiff", "--scan", "--no-color"],
                          capture_output=True, text=True, encoding="utf-8", cwd=project)
    assert proc.returncode == 0
    assert "Comparing" in proc.stdout
