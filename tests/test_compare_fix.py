import pytest

from envdiff.compare import all_missing, compare
from envdiff.fixer import apply, backup_path, plan
from envdiff.parser import parse_file, parse_text


def test_compare_three_buckets():
    env = parse_text("A=1\nB=2\nC=3\n", ".env")
    ex = parse_text("B=\nC=\nD=\n", ".env.example")
    d = compare(env, ex)
    assert (d.missing, d.extra, d.common) == (["A"], ["D"], ["B", "C"])
    assert not d.clean
    assert compare(ex, ex).clean


def test_all_missing_union_keeps_order():
    ex = parse_text("A=\n")
    d1 = compare(parse_text("A=1\nX=1\nY=1\n"), ex)
    d2 = compare(parse_text("Y=1\nZ=1\n"), ex)
    assert all_missing([d1, d2]) == ["X", "Y", "Z"]


def test_fix_appends_only_key_names_and_backs_up(write, fake_secrets):
    env_text = "".join(f"{k}={v}\n" for k, v in fake_secrets.items())
    env_p = write(".env", env_text)
    ex_p = write(".env.example", "OPENAI_API_KEY=\n# keep me")
    d = compare(parse_file(env_p), parse_file(ex_p))
    p = plan(str(ex_p), d.missing)
    backup = apply(p)
    assert backup and backup.endswith(".env.example.bak")
    result = ex_p.read_text(encoding="utf-8")
    assert result.startswith("OPENAI_API_KEY=\n# keep me\n")
    for k, v in fake_secrets.items():
        assert v not in result
        assert f"{k}=" in result
    assert all(line.endswith("=") for line in result.splitlines()[2:])
    # Backup is the untouched original.
    assert (ex_p.parent / ".env.example.bak").read_text(encoding="utf-8") == "OPENAI_API_KEY=\n# keep me"


def test_fix_keeps_crlf(write):
    ex_p = write(".env.example", "A=\n", newline="\r\n")
    apply(plan(str(ex_p), ["B"]))
    assert ex_p.read_bytes() == b"A=\r\nB=\r\n"


def test_fix_creates_missing_file(tmp_path):
    target = tmp_path / ".env.example"
    p = plan(str(target), ["A", "B"])
    assert p.creates_file
    assert apply(p) is None
    assert target.read_text(encoding="utf-8") == "A=\nB=\n"


def test_fix_nothing_to_do(write):
    ex_p = write(".env.example", "A=\n")
    assert apply(plan(str(ex_p), [])) is None
    assert ex_p.read_text(encoding="utf-8") == "A=\n"


def test_backup_names_do_not_overwrite(write):
    ex_p = write(".env.example", "A=\n")
    write(".env.example.bak", "old")
    assert backup_path(ex_p).name == ".env.example.bak1"


def test_plan_rejects_non_key_text(tmp_path):
    with pytest.raises(ValueError) as exc:
        plan(str(tmp_path / "x"), ["A=leak"])
    assert "leak" not in str(exc.value)
