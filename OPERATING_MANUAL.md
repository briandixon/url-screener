# URL Screener — Operating Manual & Developer Guide

**Current version: 1.0.0**  ·  Versioning: [Semantic Versioning](https://semver.org/)  ·  See [§11 Version Control Workflow](#11-version-control-workflow) and [§12 Version Lineage](#12-version-lineage).

A developer-facing guide to how this app is built, how to run it, and how to
extend it. If you are new to the project, read this top to bottom once.

> **Maintainer rule:** every time you cut a new version, you MUST update §12
> Version Lineage and the `VERSION` file. That is how this app's history stays
> traceable as features are added over time.

---

## 1. What the app does

The user pastes a website URL into a web page. The app:

1. Fetches the page's HTML.
2. Extracts the **title** and **meta description**.
3. Generates a short **auto-summary** from the page's own visible text.
4. Shows the **title, description, and summary** in a clean UI.
5. Lets the user **clear** the results and try another URL.

There is **no external AI service and no API key**. All summarization happens
locally with plain Python, so the app runs fully offline (aside from fetching
the target page itself).

---

## 2. Project structure

```
URLScreener/
├── app.py               # Flask backend + all extraction/summarization logic
├── templates/
│   └── index.html       # The single-page web UI (HTML + CSS + JS)
├── requirements.txt     # Python dependencies (Flask, requests)
└── OPERATING_MANUAL.md  # This guide
```

That's the whole app — two source files. Flask automatically looks for HTML
templates inside a folder named `templates/`, which is why `index.html` lives
there.

---

## 3. Setup & running it

### Prerequisites
- Python 3.9+ (developed on Python 3.14).

### First-time setup
Open a terminal in the project folder and run:

```powershell
# (Optional but recommended) create an isolated environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

### Start the app
```powershell
python app.py
```
You'll see Flask start on **http://127.0.0.1:5000**. Open that in a browser.

To stop the app, press `Ctrl + C` in the terminal.

---

## 4. How a request flows through the system

Understanding this end-to-end path is the fastest way to learn the codebase.

```
Browser (index.html)
   │  user submits a URL
   │  fetch("/screen", POST, {url})
   ▼
Flask route  screen()           ── app.py
   │  calls screen_url(raw_url)
   ▼
screen_url()  — the orchestrator
   ├─ normalize_url()      add https:// if missing
   ├─ is_valid_url()       sanity-check scheme + host
   ├─ fetch_page()         download HTML with requests
   ├─ extract_details()    regex out <title> + meta description
   ├─ extract_visible_text() strip tags/scripts to plain text
   └─ summarize_text()     score sentences, pick the best few
   ▼
returns a JSON dict { ok, url, domain, title, description, summary }
   ▼
Browser renders the fields and shows the "Clear results" button
```

---

## 5. The backend (`app.py`) explained

The file is organized as a pipeline, with one function per step. Each is small
and independently testable.

| Function | Responsibility |
|---|---|
| `normalize_url(raw)` | Adds a `https://` scheme if the user omitted it. |
| `is_valid_url(url)` | Confirms we have a real scheme and host. |
| `fetch_page(url)` | Downloads the page; returns `(html, final_url)` after redirects. |
| `extract_details(html)` | Regex-extracts the `<title>` and `<meta name="description">` (falls back to Open Graph `og:description`). |
| `extract_visible_text(html)` | Removes `<script>`/`<style>`/comments/tags and collapses whitespace. |
| `split_sentences(text)` | Splits text into sentences on `.!?`. |
| `summarize_text(text)` | The summarizer (see below). |
| `screen_url(raw)` | Orchestrates all of the above and handles errors. |

### The summarization algorithm (extractive frequency scoring)
This is the heart of the app. It does **not** generate new prose; it **selects**
the most representative sentences already on the page:

1. Count how often each meaningful word (3+ letters, not a stop-word) appears
   across the whole page → `word_frequencies`.
2. For each candidate sentence, sum the frequencies of its words and divide by
   `(peak_frequency × sentence_length)`. Dividing keeps very long sentences from
   automatically winning.
3. Only consider the first ~30 sentences (the main content is usually near the
   top) and skip sentences that are too short or too long.
4. Take the top 3 scoring sentences, then **restore their original order** so
   the summary reads naturally.

Why this approach: it's transparent, dependency-free, deterministic, and needs
no API key. The trade-off is that it reuses the page's wording rather than
writing a fresh paraphrase.

### Error handling
`screen_url()` catches each `requests` exception type (timeout, SSL, connection,
HTTP status, generic) and returns a friendly `{ "ok": False, "error": "..." }`.
The UI shows whatever message comes back, so add new cases here if needed.

### Routes
- `GET /` → renders `templates/index.html`.
- `POST /screen` → accepts `{"url": "..."}` JSON, returns the result JSON.

---

## 6. The frontend (`templates/index.html`) explained

A single self-contained file: HTML structure, CSS in a `<style>` block, and
vanilla JavaScript in a `<script>` block (no build step, no frameworks).

- **CSS design tokens** live in `:root` (`--accent`, `--radius`, etc.). Change
  the look from there.
- **UI states** are toggled by adding/removing the `.hidden` class: loading
  spinner, error box, and results section.
- **JS flow**: on submit it POSTs to `/screen`, shows a spinner, then either
  fills in the result fields or shows the error. The **Clear results** button
  empties the input and hides the results so the user can try a new URL.

The JS talks to the backend purely through the `/screen` JSON endpoint, so the
frontend and backend are loosely coupled — you can change one without breaking
the other as long as the JSON shape stays the same.

---

## 7. How to add new features

Here are common extensions and exactly where they'd go.

### Add a new output field (e.g. word count or top keywords)
1. **Backend:** compute the value inside `screen_url()` and add it to the
   returned dict, e.g. `"word_count": len(visible_text.split())`.
2. **Frontend:** add a new `.field` block in the results section of
   `index.html`, give the value element an `id`, grab it in the JS, and set its
   `.textContent` from `data.word_count`.

### Show key topics / keywords
You already compute `word_frequencies` inside `summarize_text()`. Refactor that
counting into its own function (e.g. `keyword_frequencies(text)`), return the
top N words from `screen_url()`, and render them as tags in the UI.

### Swap in an AI-written summary later
Replace the body of `summarize_text()` (or branch inside `screen_url()`) with a
call to an LLM API. Keep the same function signature so nothing else changes.
Read the API key from an environment variable (`os.environ`) rather than
hard-coding it.

### Better HTML parsing
The current parser uses regex, which is fine for titles/meta/text but brittle
for complex pages. For robustness, add `beautifulsoup4` to `requirements.txt`
and rewrite `extract_details` / `extract_visible_text` using BeautifulSoup.

### Capture a screenshot or favicon, cache results, add history
- Caching: wrap `screen_url` with a dict or `functools.lru_cache` keyed by URL.
- History: store past results in a small SQLite DB and add a `/history` route.

---

## 8. Testing tips

Because each step is a pure function, you can test them in a Python shell:

```python
from app import summarize_text, extract_details, normalize_url

normalize_url("example.com")          # -> "https://example.com"
extract_details("<title>Hi</title>")  # -> {"title": "Hi", "description": ""}
summarize_text("Sentence one. Sentence two. ...")
```

For end-to-end checks, run the app and try:
- A normal site (e.g. a news article) → expect a real summary.
- A bare domain with no scheme (`example.com`) → should still work.
- A non-existent domain → should show a friendly connection error.

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `ModuleNotFoundError: flask` | Run `pip install -r requirements.txt` (and activate your venv). |
| Browser says "Could not reach the server" | The Flask app isn't running, or it's on a different port. |
| A site returns an HTTP 403 error | Some sites block automated requests; try another URL. The `User-Agent` header in `app.py` already mimics a browser to reduce this. |
| Summary is empty | The page had little extractable text (e.g. heavily JavaScript-rendered). The app reads server-delivered HTML only; it does not run page JS. |
| Port 5000 already in use | Change the port in the last line of `app.py` (`app.run(..., port=5001)`). |

---

## 10. Key design decisions (the "why")

- **Local extractive summary, no API key** — zero setup, no cost, no secrets to
  manage, runs offline. Chosen deliberately over an AI API per the project's
  requirements.
- **Single Flask app serving both UI and API** — simplest possible deployment:
  one command, one process, one URL.
- **One function per pipeline step** — easy to read, test, and replace pieces
  (e.g. swap the summarizer) without touching the rest.
- **Vanilla JS, no build tooling** — the HTML file just works; no Node, bundler,
  or framework to learn or maintain.

---

## 11. Version Control Workflow

This project is tracked with Git and hosted on GitHub. Versions are managed with
**Semantic Versioning** and **Git tags**, and each version is published as a
**GitHub Release**, so any past version can be accessed and run.

### 11.1 Semantic Versioning (SemVer)

Versions are `MAJOR.MINOR.PATCH` (e.g. `1.4.2`):

| Part | Bump it when… | Example |
|---|---|---|
| **MAJOR** | You make a breaking/incompatible change (e.g. change the `/screen` JSON shape, drop a feature). | `1.x.x → 2.0.0` |
| **MINOR** | You add new functionality in a backward-compatible way (e.g. a new output field like keywords). | `1.0.0 → 1.1.0` |
| **PATCH** | You make a backward-compatible bug fix or docs/typo fix. | `1.0.0 → 1.0.1` |

The single source of truth for the current number is the **`VERSION`** file at
the repo root. Keep it, the tag, and §12 in sync.

### 11.2 The single source of truth: `VERSION`

`VERSION` contains just the number (e.g. `1.0.0`). When releasing, bump it first,
then tag with a `v` prefix (`v1.0.0`). The README badge should match.

### 11.3 Day-to-day: branch + pull request flow

Keep `main` always runnable. Build each feature on its own branch:

```bash
git checkout main && git pull
git checkout -b feature/keyword-extraction   # one branch per feature/fix

# ...make changes, commit as you go...
git add -A
git commit -m "feat: add keyword extraction to results"

git push -u origin feature/keyword-extraction
gh pr create --fill            # open a Pull Request for review
# after review/merge on GitHub:
git checkout main && git pull
```

Suggested branch prefixes: `feature/…`, `fix/…`, `docs/…`, `chore/…`.

### 11.4 Commit message style

Short, imperative, and prefixed by type so history reads cleanly and can later
feed an automated changelog:

```
feat: add word-count field to the result panel
fix: handle pages with no <title> tag
docs: clarify summarizer algorithm in the manual
chore: bump dependencies
```

### 11.5 Cutting a new release (the checklist)

Do these in order every time you ship a version — this is what keeps lineage
intact:

1. Merge all the version's changes into `main`; make sure the app runs.
2. **Update `VERSION`** to the new number (e.g. `1.1.0`).
3. **Update §12 Version Lineage** below with a new row + an Added/Changed/Fixed list.
4. Update the README version badge and the "Current version" line at the top of
   this manual.
5. Commit those doc/version bumps:
   ```bash
   git add VERSION README.md OPERATING_MANUAL.md
   git commit -m "chore(release): v1.1.0"
   ```
6. **Tag and push:**
   ```bash
   git tag -a v1.1.0 -m "v1.1.0 — keyword extraction"
   git push origin main
   git push origin v1.1.0
   ```
7. **Publish a GitHub Release** from the tag (attaches downloadable source so the
   version is easy to access):
   ```bash
   gh release create v1.1.0 --title "v1.1.0" --notes "Keyword extraction + word count."
   ```

### 11.6 Accessing / running an older version

```bash
git tag                 # list every released version
git checkout v1.0.0     # switch the working tree to that version
python app.py           # run it
git checkout main       # return to latest
```
Or download a version's source zip from the GitHub **Releases** page — no Git
required.

---

## 12. Version Lineage

The authoritative, human-readable history of the app. **Add a new entry here as
the first step of every release** (see §11.5). Newest version on top.

> Format follows the spirit of [Keep a Changelog](https://keepachangelog.com/):
> group notes under **Added / Changed / Fixed / Removed**.

| Version | Date | Git tag | Summary |
|---|---|---|---|
| **1.0.0** | 2026-06-05 | `v1.0.0` | Initial release. |

### 1.0.0 — 2026-06-05 — `v1.0.0`
**Added**
- Flask web app with a single-page UI (`templates/index.html`).
- URL input with optional scheme; normalization and validation.
- Page fetching via `requests` with a browser User-Agent and timeout.
- Extraction of page **title** and **meta description** (Open Graph fallback).
- Local **extractive auto-summary** using word-frequency sentence scoring.
- **Clear results** action to reset and try a new URL.
- Friendly error handling (timeout, SSL, connection, HTTP status, generic).
- Operating manual, README, MIT license, and SemVer + Git-tag release workflow.

<!--
TEMPLATE — copy this block for the next release, fill it in, and add a table row.

### X.Y.Z — YYYY-MM-DD — `vX.Y.Z`
**Added**
- ...
**Changed**
- ...
**Fixed**
- ...
**Removed**
- ...
-->
```
