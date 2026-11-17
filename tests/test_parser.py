from envdiff.parser import Entry, parse_file, parse_text


def values(text):
    return {e.key: e.value for e in parse_text(text).entries}


def test_basic_comments_and_blank_lines():
    env = parse_text("# comment\n\nA=1\n   # indented comment\nB=two\n")
    assert env.keys == ["A", "B"]
    assert env.issues == []


def test_export_prefix_and_spaces_around_equals():
    assert values("export A=1\nexport   B = 2\n  C =3\n") == {"A": "1", "B": "2", "C": "3"}


def test_quotes_and_hash_inside_quotes():
    v = values('A="has # hash"\nB=\'single # too\'\nC=`back`\n')
    assert v == {"A": "has # hash", "B": "single # too", "C": "back"}


def test_inline_comment_and_hash_without_space():
    v = values("A=value # comment\nB=abc#def\nC= # only comment\nD=\n")
    assert v == {"A": "value", "B": "abc#def", "C": "", "D": ""}


def test_equals_inside_value():
    assert values("URL=postgres://h/db?a=1&b=2\n")["URL"] == "postgres://h/db?a=1&b=2"


def test_double_quote_escapes_single_quote_literal():
    v = values('A="line\\nnext \\"q\\" \\\\ \\x"\nB=\'raw\\n\'\n')
    assert v["A"] == 'line\nnext "q" \\ \\x'
    assert v["B"] == "raw\\n"


def test_multiline_values():
    env = parse_text('KEY="first\nsecond\nthird"\nAFTER=1\nS=\'a\nb\'\n')
    v = {e.key: e.value for e in env.entries}
    assert v["KEY"] == "first\nsecond\nthird"
    assert v["S"] == "a\nb"
    assert [e.line for e in env.entries] == [1, 4, 5]


def test_unterminated_quote_reports_line_only_and_recovers():
    env = parse_text('A=1\nB="never closed\nC=3\n')
    # B is skipped, parsing continues on the next line.
    assert "C" in env.keys and "B" not in env.keys
    assert [(i.line, i.key) for i in env.issues] == [(2, "B")]


def test_invalid_lines_never_echo_content():
    secret_ish = "ghp_" + "Qz8vR2mK9tLw4XpB7nYc3HdJ6sFg1234"
    env = parse_text(f"{secret_ish}\n=nokey\n!!!\n")
    assert [i.line for i in env.issues] == [1, 2, 3]
    for issue in env.issues:
        assert issue.key is None
        assert secret_ish not in issue.message


def test_duplicates_flagged_last_wins():
    env = parse_text("A=1\nB=2\nA=3\n")
    assert env.keys == ["A", "B"]
    assert env.last()["A"].value == "3"
    assert env.issues[0].line == 3 and env.issues[0].key == "A"
    assert "line 1" in env.issues[0].message


def test_entry_repr_hides_value():
    assert "s3cr3t" not in repr(Entry("A", 1, "s3cr3t"))


def test_crlf_bom_and_non_utf8(write):
    p = write(".env", "\ufeffA=1\nB=\"x\"\n", newline="\r\n")
    assert parse_file(p).keys == ["A", "B"]
    q = write(".env2", "")
    q.write_bytes(b"C=\xff\xfe\nD=ok\n")
    env = parse_file(q)
    assert env.keys == ["C", "D"] and env.issues == []


def test_dotted_and_dashed_keys():
    assert parse_text("app.name=x\nsome-key=y\n").keys == ["app.name", "some-key"]
