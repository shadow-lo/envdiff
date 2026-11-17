<div align="center">

# 🔐 envdiff

**Keep `.env` and `.env.example` in sync, and catch real secrets in the example file, without ever printing a value.**

[![test](https://github.com/shadow-lo/envdiff/actions/workflows/test.yml/badge.svg)](https://github.com/shadow-lo/envdiff/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![Offline](https://img.shields.io/badge/network-none-lightgrey)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

[Türkçe](README.tr.md)

<img src="docs/img/hero.svg" alt="envdiff terminal output" width="760">

</div>

## ✨ Why

Someone adds a key to `.env` and forgets `.env.example`. The next developer clones the repo and the app will not start. Worse, someone pastes a real API key into `.env.example` and it gets committed.

`envdiff` compares the two files **by key name only**, tells you what is missing or extra, flags values that look like real secrets, and can add the missing keys for you with empty values. It runs offline and has no network code at all.

## 📦 Install

```bash
pip install envdiff      # or: pipx install envdiff
```

Python 3.9+. No dependencies.

## 🚀 Usage

```bash
envdiff                               # compare .env with .env.example
envdiff .env.production .env.example  # any two files (the last one is the reference)
envdiff --check --scan                # for CI: exit 1 on any difference or likely secret
envdiff --fix                         # preview, then add missing keys with empty values
envdiff .env.development .env.production --example .env.example --json
```

## ⚙️ Options

| Option | Description |
|---|---|
| `FILE ...` | Env files to compare. None: `.env`. With 2+ files the last one is the reference |
| `--example PATH` | Reference file (default `.env.example`) |
| `--check` | Exit `1` if keys differ, a line cannot be parsed, or (with `--scan`) a secret is found |
| `--scan` | Look for real-looking secrets in the reference file |
| `--fix` | Append missing keys to the reference file as `KEY=` (preview first, then asks) |
| `--dry-run` | With `--fix`: only show what would be added |
| `-y`, `--yes` | With `--fix`: write without asking (for scripts) |
| `--json` | JSON output (no color) |
| `--no-color` | Plain output. `NO_COLOR` is respected too |

**Exit codes:** `0` OK (or differences found without `--check`), `1` `--check` failed, `2` error (missing file, bad arguments).

## 🛡️ Security rules

This is the point of the tool, so the rules are strict and tested:

- **Values never appear in any output:** terminal, `--json`, or error messages. Only key names and line numbers are shown.
- **Secret findings are masked.** At most a public format prefix is shown, like `sk-****` or `AKIA****`.
- **Errors show a line number, never the line.** A broken line is reported as `line 7: invalid line`, not echoed back.
- **`--fix` copies key names only.** It writes `KEY=` and nothing from your real `.env`. It previews first, asks before writing, and saves a backup (`.env.example.bak`).
- **No network code.** Nothing is sent anywhere.
- **The test suite uses fake secrets only**, and checks every output mode for leaked values.

## 🔎 What `--scan` looks for

| Severity | Rule |
|---|---|
| high | Known key formats: OpenAI/Anthropic `sk-`, GitHub `ghp_`/`github_pat_`, AWS `AKIA`, Stripe `sk_live_`, Google `AIza`, Slack `xox*-`, GitLab `glpat-`, JWTs, private key blocks |
| medium | Long high-entropy strings, URLs with an embedded password (`postgres://user:pass@...`) |
| low | Names containing `KEY`, `SECRET`, `TOKEN`, `PASSWORD`... with a filled-in value |

Placeholders are **not** flagged: `your-key-here`, `changeme`, `<token>`, `${VAR}`, `xxxx`, `REPLACE_ME`, `example`, empty values, numbers and booleans.

<details>
<summary>📋 Example JSON output</summary>

```json
{
  "reference": ".env.example",
  "files": [
    {"path": ".env", "missing": ["REDIS_URL"], "extra": ["LEGACY_API_URL"],
     "common_count": 3, "in_sync": false}
  ],
  "scan": {"path": ".env.example", "findings": [
    {"line": 7, "key": "OPENAI_API_KEY", "severity": "high",
     "reason": "matches a known OpenAI-style API key pattern", "masked": "sk-****"}
  ]},
  "parse_warnings": [],
  "summary": {"missing": 1, "extra": 1, "secrets": 1, "parse_warnings": 0},
  "ok": false
}
```

</details>

## 📝 Parsing

Handles comments, blank lines, `export` prefixes, single/double/backtick quotes, `#` inside quotes, inline comments (`KEY=value # note`), `=` inside values, escapes in double quotes, multi-line quoted values, CRLF line endings and a UTF-8 BOM. Duplicate keys are reported (the last one wins).

## ⚠️ Limitations

- `--scan` is a heuristic. It can miss a secret in an unknown format, and it can flag a harmless value (for example a long random-looking ID). Treat it as a safety net, not a guarantee.
- If a real secret was ever committed, removing it is not enough: rotate the key.
- No variable expansion (`${OTHER}` is kept as text) and no type checks yet.
- v1 has no pre-commit hook or GitHub Action (planned).

## 🧪 Development

```bash
pip install -e ".[dev]"
pytest          # fails below 80% coverage; CI runs Linux + Windows
```

## 📄 License

[MIT](LICENSE)
