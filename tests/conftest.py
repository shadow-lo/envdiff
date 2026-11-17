"""Shared test helpers.

Every "secret" in this test suite is FAKE. They are assembled from pieces at
runtime so the source never contains a string that looks like a real key to
secret scanners, and none of them has ever been a valid credential.
"""

import pytest


def _j(*parts: str) -> str:
    return "".join(parts)


# Random-looking but meaningless characters. Deliberately avoids words like
# "fake" or "example", which the scanner treats as placeholders.
NOISE = "Qz8vR2mK9tLw4XpB7nYc3HdJ6sFg"

FAKE_SECRETS = {
    "OPENAI_API_KEY": _j("sk", "-", NOISE),
    "ANTHROPIC_API_KEY": _j("sk", "-ant-", NOISE),
    "GITHUB_TOKEN": _j("gh", "p_", NOISE, "1234567890"),
    "AWS_ACCESS_KEY_ID": _j("AK", "IA", "QZ8VR2MK9TLW4XPB"),
    "STRIPE_SECRET": _j("sk", "_live_", NOISE),
    "GOOGLE_KEY": _j("AI", "za", NOISE, "abcdefgh"),
    "SLACK_BOT": _j("xo", "xb-", "1234567890-", NOISE),
    "RANDOM_BLOB": _j("Zq8", "vR2mK9tLw4XpB7nYc3HdJ6sFgA1"),
    "DB_PASSWORD": _j("hunter", "Two", "Seven"),
    "DATABASE_URL": _j("postgres://app:", "Rq7", "Lw2Zx9@db.internal:5432/app"),
}


@pytest.fixture
def fake_secrets():
    return dict(FAKE_SECRETS)


@pytest.fixture
def write(tmp_path):
    def _write(name: str, text: str, newline: str = "\n"):
        p = tmp_path / name
        p.write_bytes(text.replace("\n", newline).encode("utf-8"))
        return p
    return _write
