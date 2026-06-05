# 🔎 URL Screener

A small Flask web app: paste a website URL and get a brief **description** and an
auto-generated **summary** built entirely from the page's own content — no
external AI service and **no API key required**.

![version](https://img.shields.io/badge/version-1.0.0-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Features (v1.0.0)

- Paste any URL (scheme optional — `example.com` works).
- Extracts the page **title** and **meta description** (with Open Graph fallback).
- Generates a short **auto-summary** locally via word-frequency sentence scoring.
- Clean, responsive web UI with loading, error, and **Clear results** states.
- Friendly error handling for timeouts, bad domains, SSL issues, and HTTP errors.

---

## Quick start

```bash
# 1. (optional) create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. run
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

---

## Project structure

```
url-screener/
├── app.py               # Flask backend + extraction/summarization logic
├── templates/
│   └── index.html       # Single-page web UI
├── requirements.txt     # Python dependencies
├── VERSION              # Current version (single source of truth)
├── README.md            # This file
├── OPERATING_MANUAL.md  # Developer guide + version lineage
└── .gitignore
```

---

## Versions & releases

This project uses [Semantic Versioning](https://semver.org/) and Git tags. Every
release is tagged (`v1.0.0`) and published as a GitHub Release, so you can access
and run any past version.

- **Browse all versions:** see the *Releases* page on GitHub, or run `git tag`.
- **Run a specific version:** `git checkout v1.0.0`
- **Version history & lineage:** see [OPERATING_MANUAL.md](OPERATING_MANUAL.md) → *Version Lineage*.

---

## Documentation

Full developer documentation — architecture, how each function works, how to add
features, and the version-control workflow — lives in
**[OPERATING_MANUAL.md](OPERATING_MANUAL.md)**.

---

## License

MIT — see [LICENSE](LICENSE).
