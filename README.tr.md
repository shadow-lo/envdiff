<div align="center">

# 🔐 envdiff

**`.env` ve `.env.example` dosyalarını uyumlu tutar, örnek dosyadaki gerçek secret'ları yakalar ve hiçbir değeri ekrana yazmaz.**

[![test](https://github.com/shadow-lo/envdiff/actions/workflows/test.yml/badge.svg)](https://github.com/shadow-lo/envdiff/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Bağımlılık](https://img.shields.io/badge/ba%C4%9F%C4%B1ml%C4%B1l%C4%B1k-0-brightgreen)
![Çevrimdışı](https://img.shields.io/badge/a%C4%9F-yok-lightgrey)
[![Lisans: MIT](https://img.shields.io/badge/lisans-MIT-yellow.svg)](LICENSE)

[English](README.md)

<img src="docs/img/hero.svg" alt="envdiff terminal çıktısı" width="760">

</div>

## ✨ Neden

Biri `.env` dosyasına yeni bir anahtar ekler ama `.env.example`'ı unutur. Repoyu yeni klonlayan geliştirici uygulamayı çalıştıramaz. Daha kötüsü, biri gerçek bir API anahtarını `.env.example`'a yapıştırır ve bu commit'lenir.

`envdiff` iki dosyayı **yalnızca anahtar adlarına göre** karşılaştırır, neyin eksik veya fazla olduğunu söyler, gerçek secret'a benzeyen değerleri işaretler ve eksik anahtarları boş değerle sizin yerinize ekleyebilir. Tamamen çevrimdışı çalışır, içinde hiç ağ kodu yoktur.

## 📦 Kurulum

```bash
pip install envdiff      # veya: pipx install envdiff
```

Python 3.9+. Bağımlılık yok.

## 🚀 Kullanım

```bash
envdiff                               # .env ile .env.example'ı karşılaştır
envdiff .env.production .env.example  # herhangi iki dosya (sonuncusu referanstır)
envdiff --check --scan                # CI için: fark veya olası secret varsa çıkış kodu 1
envdiff --fix                         # önizle, sonra eksik anahtarları boş değerle ekle
envdiff .env.development .env.production --example .env.example --json
```

## ⚙️ Seçenekler

| Seçenek | Açıklama |
|---|---|
| `FILE ...` | Karşılaştırılacak env dosyaları. Verilmezse: `.env`. 2+ dosyada sonuncusu referanstır |
| `--example PATH` | Referans dosya (varsayılan `.env.example`) |
| `--check` | Anahtarlar farklıysa, bir satır ayrıştırılamıyorsa veya (`--scan` ile) secret bulunursa `1` ile çıkar |
| `--scan` | Referans dosyada gerçek görünen secret'ları arar |
| `--fix` | Eksik anahtarları referans dosyaya `KEY=` olarak ekler (önce önizler, sonra sorar) |
| `--dry-run` | `--fix` ile: yalnızca ne ekleneceğini gösterir |
| `-y`, `--yes` | `--fix` ile: sormadan yazar (betikler için) |
| `--json` | JSON çıktı (renksiz) |
| `--no-color` | Düz çıktı. `NO_COLOR` da dikkate alınır |

**Çıkış kodları:** `0` sorun yok (veya `--check` olmadan fark bulundu), `1` `--check` başarısız, `2` hata (dosya yok, hatalı argüman).

## 🛡️ Güvenlik kuralları

Aracın asıl amacı bu, o yüzden kurallar katı ve testlerle doğrulanıyor:

- **Değerler hiçbir çıktıda görünmez:** terminal, `--json` veya hata mesajları. Yalnızca anahtar adları ve satır numaraları gösterilir.
- **Secret bulguları maskelenir.** En fazla herkesin bildiği biçim öneki gösterilir: `sk-****`, `AKIA****` gibi.
- **Hatalarda satırın kendisi değil, numarası geçer.** Bozuk bir satır `line 7: invalid line` olarak bildirilir, içeriği geri yazılmaz.
- **`--fix` yalnızca anahtar adlarını kopyalar.** `KEY=` yazar, gerçek `.env` dosyanızdan hiçbir şey almaz. Önce önizleme gösterir, yazmadan önce sorar ve yedek alır (`.env.example.bak`).
- **Ağ kodu yok.** Hiçbir şey hiçbir yere gönderilmez.
- **Testlerde yalnızca sahte secret'lar kullanılır** ve her çıktı modu değer sızıntısına karşı denetlenir.

## 🔎 `--scan` neye bakar

| Önem | Kural |
|---|---|
| high | Bilinen anahtar biçimleri: OpenAI/Anthropic `sk-`, GitHub `ghp_`/`github_pat_`, AWS `AKIA`, Stripe `sk_live_`, Google `AIza`, Slack `xox*-`, GitLab `glpat-`, JWT'ler, private key blokları |
| medium | Uzun, yüksek entropili dizeler, içinde parola olan URL'ler (`postgres://user:pass@...`) |
| low | Adında `KEY`, `SECRET`, `TOKEN`, `PASSWORD`... geçen ve değeri dolu olanlar |

Yer tutucular secret **sayılmaz**: `your-key-here`, `changeme`, `<token>`, `${VAR}`, `xxxx`, `REPLACE_ME`, `example`, boş değerler, sayılar ve true/false.

<details>
<summary>📋 Örnek JSON çıktısı</summary>

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

## 📝 Ayrıştırma

Yorumları, boş satırları, `export` önekini, tek/çift/ters tırnakları, tırnak içindeki `#` işaretini, satır sonu yorumlarını (`KEY=value # not`), değer içindeki `=` işaretini, çift tırnaktaki kaçış karakterlerini, çok satırlı tırnaklı değerleri, CRLF satır sonlarını ve UTF-8 BOM'u destekler. Tekrarlanan anahtarlar bildirilir (sonuncusu geçerlidir).

## ⚠️ Sınırlamalar

- `--scan` sezgiseldir. Bilinmeyen biçimdeki bir secret'ı kaçırabilir veya zararsız bir değeri (örneğin uzun, rastgele görünen bir kimlik) işaretleyebilir. Garanti değil, güvenlik ağı olarak düşünün.
- Gerçek bir secret bir kez commit'lendiyse silmek yetmez: anahtarı yenileyin.
- Değişken genişletme yok (`${OTHER}` metin olarak kalır) ve henüz tip denetimi yok.
- v1'de pre-commit hook'u ve GitHub Action yok (planlandı).

## 🧪 Geliştirme

```bash
pip install -e ".[dev]"
pytest          # kapsam %80'in altına düşerse başarısız olur; CI Linux + Windows'ta çalışır
```

## 📄 Lisans

[MIT](LICENSE)
