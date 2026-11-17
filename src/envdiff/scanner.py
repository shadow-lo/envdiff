"""Look for values in an example file that look like real secrets.

A finding never contains the value. `masked` shows at most a well-known,
non-secret prefix (like ``sk-``) followed by ``****``.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .parser import EnvFile

MASK = "****"

# (name, regex, prefix shown in the mask). Prefixes are public format markers, not secret data.
KNOWN_PATTERNS: List[Tuple[str, "re.Pattern[str]", str]] = [
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "-----BEGIN "),
    ("Anthropic API key", re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,}"), "sk-ant-"),
    ("OpenAI-style API key", re.compile(r"^sk-(proj-)?[A-Za-z0-9_\-]{20,}"), "sk-"),
    ("Stripe live key", re.compile(r"^(sk|rk)_live_[A-Za-z0-9]{16,}"), "sk_live_"),
    ("GitHub token", re.compile(r"^(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}"), "gh*_"),
    ("GitHub fine-grained token", re.compile(r"^github_pat_[A-Za-z0-9_]{30,}"), "github_pat_"),
    ("GitLab token", re.compile(r"^glpat-[A-Za-z0-9_\-]{20,}"), "glpat-"),
    ("AWS access key id", re.compile(r"^(AKIA|ASIA)[A-Z0-9]{16}$"), "AKIA"),
    ("Google API key", re.compile(r"^AIza[A-Za-z0-9_\-]{30,}"), "AIza"),
    ("Slack token", re.compile(r"^xox[abposr]-[A-Za-z0-9\-]{10,}"), "xox*-"),
    ("JSON Web Token", re.compile(r"^eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."), "eyJ"),
]

CRED_URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://([^:/@\s]+):([^@/\s]+)@")
SENSITIVE_NAME_RE = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|PRIVATE|CREDENTIAL", re.I)

PLACEHOLDER_WORDS = (
    "changeme", "change-me", "change_me", "replace", "your", "example", "placeholder",
    "dummy", "sample", "fake", "redacted", "insert", "todo", "tbd", "fixme", "xxx", "<", "${", "{{",
)
PLACEHOLDER_EXACT = {
    "", "none", "null", "nil", "true", "false", "yes", "no", "on", "off",
    "secret", "password", "pass", "token", "key", "test", "testing", "dev", "local",
    "localhost", "admin", "root", "user", "default", "empty", "-", "...",
}
PLACEHOLDER_RE = re.compile(r"^(x+|\*+|\.+|_+|-+|0+|\$[A-Za-z_][A-Za-z0-9_]*|.*[-_ ]here)$", re.I)


@dataclass
class Finding:
    line: int
    key: str
    severity: str  # "high" | "medium" | "low"
    reason: str
    masked: str


def is_placeholder(value: str) -> bool:
    v = value.strip().lower()
    if v in PLACEHOLDER_EXACT or PLACEHOLDER_RE.match(v):
        return True
    if v.isdigit():
        return True
    return any(w in v for w in PLACEHOLDER_WORDS)


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def looks_random(value: str) -> bool:
    """Long, high-entropy, token-like string."""
    v = value.strip()
    if len(v) < 20 or any(ch.isspace() for ch in v) or "://" in v:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/=_\-.~]+", v):
        return False
    has_digit = any(ch.isdigit() for ch in v)
    has_alpha = any(ch.isalpha() for ch in v)
    if not (has_digit and has_alpha):
        return False
    if re.fullmatch(r"[0-9a-fA-F]+", v):
        return len(v) >= 32 and shannon_entropy(v) >= 3.0
    return shannon_entropy(v) >= 4.0


def classify(key: str, value: str) -> Optional[Finding]:
    """Return a Finding (with line 0) or None. Never stores the value."""
    v = value.strip()
    if not v:
        return None
    for name, rx, prefix in KNOWN_PATTERNS:
        if rx.search(v):
            # A known shape that is clearly filled with placeholder text is fine.
            if name != "private key block" and is_placeholder(v):
                return None
            return Finding(0, key, "high", f"matches a known {name} pattern", prefix + MASK)
    if is_placeholder(v):
        return None
    m = CRED_URL_RE.match(v)
    if m:
        if is_placeholder(m.group(2)):
            return None
        return Finding(0, key, "medium", "URL with an embedded password", MASK)
    if looks_random(v):
        return Finding(0, key, "medium", "long high-entropy string", MASK)
    if SENSITIVE_NAME_RE.search(key):
        return Finding(0, key, "low", "sensitive-looking name with a filled-in value", MASK)
    return None


def scan(env: EnvFile) -> List[Finding]:
    findings = []
    for entry in env.entries:
        f = classify(entry.key, entry.value)
        if f:
            f.line = entry.line
            findings.append(f)
    return findings
