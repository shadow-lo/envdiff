import pytest

from envdiff.parser import parse_text
from envdiff.scanner import classify, is_placeholder, looks_random, scan, shannon_entropy


@pytest.mark.parametrize("key", [
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN", "AWS_ACCESS_KEY_ID",
    "STRIPE_SECRET", "GOOGLE_KEY", "SLACK_BOT",
])
def test_known_patterns_are_high_and_masked(key, fake_secrets):
    f = classify(key, fake_secrets[key])
    assert f is not None and f.severity == "high"
    assert f.masked.endswith("****")
    assert fake_secrets[key] not in f.masked
    assert fake_secrets[key][6:] not in f.masked + f.reason


def test_anthropic_beats_generic_sk(fake_secrets):
    assert classify("K", fake_secrets["ANTHROPIC_API_KEY"]).masked == "sk-ant-****"


def test_private_key_block():
    f = classify("PEM", "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----")
    assert f.severity == "high" and f.masked == "-----BEGIN ****"


def test_high_entropy_and_credential_url(fake_secrets):
    assert classify("BLOB", fake_secrets["RANDOM_BLOB"]).reason == "long high-entropy string"
    f = classify("DATABASE_URL", fake_secrets["DATABASE_URL"])
    assert f.severity == "medium" and f.masked == "****"


def test_sensitive_name_with_value(fake_secrets):
    f = classify("DB_PASSWORD", fake_secrets["DB_PASSWORD"])
    assert f.severity == "low"


@pytest.mark.parametrize("value", [
    "", "your-key-here", "changeme", "CHANGE_ME", "<your token>", "${OTHER_VAR}", "$OTHER",
    "xxxxxxxx", "********", "sk-your-key-here", "REPLACE_ME", "example", "dummy",
    "secret", "password", "todo", "put-it-here", "{{ token }}", "AKIA" + "IOSFODNN7EXAMPLE",
])
def test_placeholders_are_not_secrets(value):
    assert classify("API_SECRET_KEY", value) is None


@pytest.mark.parametrize("value", ["3600", "true", "localhost"])
def test_harmless_values_on_sensitive_names(value):
    assert classify("TOKEN_TTL", value) is None


def test_placeholder_password_in_url():
    assert classify("DATABASE_URL", "postgres://user:changeme@localhost/db") is None
    assert classify("DATABASE_URL", "postgres://localhost/db") is None


def test_plain_config_not_flagged():
    for k, v in {"PORT": "8080", "DEBUG": "false", "APP_NAME": "my shop",
                 "API_URL": "https://api.example.org/v1/resources/items"}.items():
        assert classify(k, v) is None


def test_looks_random_edges():
    assert not looks_random("short1A")
    assert not looks_random("a" * 30 + "1")            # low entropy
    assert not looks_random("onlyletterslongenoughstring")
    assert not looks_random("has space 1234567890abcdefgh")
    assert not looks_random("abc!@#123456789012345678")
    assert looks_random("9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08")
    assert not looks_random("0123456789abcdef0123")    # hex too short
    assert shannon_entropy("") == 0.0


def test_is_placeholder_digits():
    assert is_placeholder("12345")


def test_scan_sets_line_numbers(fake_secrets):
    env = parse_text(f"# c\nPORT=1\nGITHUB_TOKEN={fake_secrets['GITHUB_TOKEN']}\nAPI_KEY=\n")
    findings = scan(env)
    assert [(f.line, f.key) for f in findings] == [(3, "GITHUB_TOKEN")]
