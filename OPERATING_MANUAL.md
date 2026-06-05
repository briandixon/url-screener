# URL Screener — Operating Manual & Developer Guide

**Current version: 1.1.1**  ·  Versioning: [Semantic Versioning](https://semver.org/)  ·  See [§11 Version Control Workflow](#11-version-control-workflow), [§12 Version Lineage](#12-version-lineage), and [§13 YouTube Data API Setup](#13-youtube-data-api-setup).

A developer-facing guide to how this app is built, how to run it, and how to
extend it. If you are new to the project, read this top to bottom once.

> **Maintainer rule:** every time you cut a new version, you MUST update §12
> Version Lineage and the `VERSION` file. That is how this app's history stays
> traceable as features are added over time.

---

## 1. What the app does

The app has **one smart input field** that accepts either a **website URL** or a
**YouTube channel** (name, `@handle`, or channel URL) and auto-detects which.

**For a website** (no API key needed):
1. Fetches the page's HTML.
2. Extracts the **title** and **meta description**.
3. Generates a short **auto-summary** from the page's own visible text.

**For a YouTube channel** (uses the YouTube Data API v3 — see §13):
1. Resolves the channel from a name/handle/URL.
2. Fetches its **overview** (title, handle, about text) and **links/creator info**
   (avatar, banner, country, join date, channel link).
3. Generates an **auto-summary** of the channel's description.

In both cases the result is shown in a clean UI, and the user can **clear** the
results to try another input. Website summarization runs fully locally; only the
YouTube feature calls an external API.

---

## 2. Project structure

```
url-screener/
├── app.py               # Flask backend: routing + website screening
├── summarizer.py        # Shared extractive text-summarizer (used by both features)
├── youtube_api.py       # YouTube channel lookup via YouTube Data API v3
├── templates/
│   └── index.html       # The single-page web UI (HTML + CSS + JS)
├── requirements.txt     # Python dependencies (Flask, requests, python-dotenv)
├── .env.example         # Template for local secrets (copy to .env)
├── VERSION              # Current version string (single source of truth)
├── README.md            # Project overview / quick start
└── OPERATING_MANUAL.md  # This guide
```

Flask automatically looks for HTML templates inside a folder named `templates/`,
which is why `index.html` lives there.

**How the modules relate:**
- `app.py` owns the Flask routes and the website pipeline. Its `dispatch_input()`
  decides website vs YouTube and calls the right handler.
- `youtube_api.py` owns everything YouTube. It imports the shared summarizer.
- `summarizer.py` holds the text helpers (`extract_visible_text`, `summarize_text`)
  so both features share one implementation with no duplication or circular imports.

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

### Optional: configure the YouTube key
The website feature needs no setup. For the **YouTube** feature, copy the secrets
template and add your key (see §13 for how to get one):

```powershell
Copy-Item .env.example .env
# then edit .env and set YOUTUBE_API_KEY=...
```
`app.py` loads `.env` on startup via `python-dotenv`, so the key is picked up
automatically. `.env` is gitignored and never committed.

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
   │  user submits a URL or YouTube channel
   │  fetch("/screen", POST, {url})
   ▼
Flask route  screen()              ── app.py
   │  calls dispatch_input(raw)
   ▼
dispatch_input()  — picks the handler
   │  youtube_api.looks_like_youtube(raw)?
   ├─ NO  → screen_url(raw)                     (website pipeline, app.py)
   │         ├─ normalize_url / is_valid_url
   │         ├─ fetch_page()        download HTML with requests
   │         ├─ extract_details()   regex out <title> + meta description
   │         ├─ extract_visible_text()  (summarizer.py)
   │         └─ summarize_text()        (summarizer.py)
   │         ▼  { ok, type:"website", url, domain, title, description, summary }
   │
   └─ YES → youtube_api.screen_channel(raw)     (YouTube pipeline)
             ├─ resolve_channel_id()  name/@handle/URL → channel id (Data API)
             ├─ _fetch_channel()      channels.list (snippet + branding)
             └─ summarize_text()      (summarizer.py)
             ▼  { ok, type:"youtube", title, handle, description, summary,
                  channel_url, avatar, banner, country, published }
   ▼
Browser renders the fields and shows the "Clear results" button
```

---

## 5. The backend explained

The code is split into three small modules, each with one job:

- **`app.py`** — Flask routes, the website pipeline, and the input dispatcher.
- **`summarizer.py`** — the shared text/summary helpers (used by both features).
- **`youtube_api.py`** — the YouTube channel pipeline (documented in §13).

### `app.py` functions

| Function | Responsibility |
|---|---|
| `normalize_url(raw)` | Adds a `https://` scheme if the user omitted it. |
| `is_valid_url(url)` | Confirms we have a real scheme and host. |
| `fetch_page(url)` | Downloads the page; returns `(html, final_url)` after redirects. |
| `extract_details(html)` | Regex-extracts the `<title>` and `<meta name="description">` (falls back to Open Graph `og:description`). |
| `screen_url(raw)` | Website orchestrator; returns a result dict with `type:"website"`. |
| `dispatch_input(raw)` | **The router.** Calls `youtube_api.looks_like_youtube()`; sends the input to the YouTube handler or the website handler. |

### `summarizer.py` functions (shared)

| Function | Responsibility |
|---|---|
| `extract_visible_text(html)` | Removes `<script>`/`<style>`/comments/tags and collapses whitespace. |
| `split_sentences(text)` | Splits text into sentences on `.!?`. |
| `summarize_text(text)` | The extractive summarizer (see below). |

> These three lived in `app.py` in v1.0.0. They moved to `summarizer.py` in
> v1.1.0 so the YouTube feature can reuse them without duplication. Behavior is
> unchanged.

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
| **1.1.1** | 2026-06-05 | `v1.1.1` | Fix: load `.env` from the app directory regardless of CWD. |
| **1.1.0** | 2026-06-05 | `v1.1.0` | YouTube channel lookup; one auto-detecting input field. |
| **1.0.0** | 2026-06-05 | `v1.0.0` | Initial release. |

### 1.1.1 — 2026-06-05 — `v1.1.1`
**Fixed**
- `app.py` now loads the `.env` next to it via `Path(__file__)` instead of
  relying on the current working directory, so `YOUTUBE_API_KEY` is found no
  matter which folder the app is launched from.

### 1.1.0 — 2026-06-05 — `v1.1.0`
**Added**
- **YouTube channel lookup** (`youtube_api.py`) via the YouTube Data API v3:
  resolve a channel from a name, `@handle`, or channel URL and return its
  overview (title, handle, about, auto-summary) plus links/creator info
  (avatar, banner, country, join date, channel link).
- **One auto-detecting input field** — `dispatch_input()` routes the input to
  the website or YouTube handler; `looks_like_youtube()` does the detection.
- UI help text listing accepted inputs, and a dedicated YouTube result layout
  (banner, avatar, meta row, links).
- `.env` support via `python-dotenv`; `.env.example` template; §13 setup guide.
- API-specific error handling (missing key, HTTP 403/quota, timeouts, no match).

**Changed**
- Extracted the shared text helpers (`extract_visible_text`, `split_sentences`,
  `summarize_text`) from `app.py` into a new **`summarizer.py`** module so both
  features reuse one implementation. Website behavior is unchanged.
- Every result now carries a `type` field (`"website"` or `"youtube"`) so the
  front-end knows which layout to render.

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

---

## 13. YouTube Data API Setup

The YouTube channel feature uses the official **YouTube Data API v3**. Websites
work without any of this — you only need a key to look up YouTube channels.

### 13.1 Get a free API key (about 2 minutes)

1. Go to the **Google Cloud Console**: <https://console.cloud.google.com/>.
2. Create a project (top bar → project dropdown → **New Project**), or pick an
   existing one.
3. Open **APIs & Services → Library**, search for **“YouTube Data API v3”**, and
   click **Enable**.
4. Open **APIs & Services → Credentials → Create credentials → API key**.
5. Copy the key. (Recommended: click **Edit** on the key → under *API restrictions*
   restrict it to **YouTube Data API v3** so it can't be misused.)

> The API has a generous **free daily quota** (10,000 units/day). Each channel
> lookup in this app costs only a few units, so normal use stays free.

### 13.2 Tell the app about the key

Create a `.env` file in the project root (copy the template):

```powershell
Copy-Item .env.example .env
```

Edit `.env` so it reads:

```
YOUTUBE_API_KEY=AIza...your-actual-key...
```

Restart the app (`python app.py`). That's it — `app.py` loads `.env` on startup
via `python-dotenv`, and `youtube_api.get_api_key()` reads `YOUTUBE_API_KEY`.

**Security:** `.env` is listed in `.gitignore`, so your key is never committed.
Never paste a real key into `README.md`, the manual, or source files.

### 13.3 How the YouTube pipeline works (`youtube_api.py`)

| Function | Responsibility |
|---|---|
| `looks_like_youtube(text)` | Detection: true for `youtube.com`/`youtu.be` links, `@handles`, or bare channel names (anything that isn't a website domain). |
| `resolve_channel_id(raw, key)` | Turns a name/`@handle`/URL into a concrete channel id, using `channels.forHandle`, `channels.forUsername`, direct id, or `search.list`. |
| `_fetch_channel(id, key)` | Calls `channels.list` with `part=snippet,brandingSettings`. |
| `build_result(channel)` | Maps the raw API object to the dict the UI renders. |
| `screen_channel(raw)` | Orchestrates the above and handles config/API errors. |

### 13.4 Notes & limitations

- **Creator social links** (Instagram, X, etc.) are **not** exposed by the Data
  API, so the UI links to the channel itself. If you need those later, you'd have
  to scrape the channel's About page — see §7 for how to add scraping.
- **Stats and recent videos** are intentionally not shown in v1.1.0. They're easy
  to add: request `part=statistics` (subscriber/view/video counts) or call
  `search.list`/`playlistItems.list` for recent videos, then surface the fields
  in `build_result()` and the UI (see §7 “Add a new output field”).
