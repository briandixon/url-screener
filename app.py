"""
URL Screener
============

A small Flask web app with one smart input field that accepts EITHER:

  * a website URL  -> returns the page title, meta description, and a local
    auto-summary built from the page's own content (no API key required), or
  * a YouTube channel (name, @handle, or channel URL) -> returns a channel
    overview, links/creator info, and an auto-summary (uses the YouTube Data
    API v3; see youtube_api.py and OPERATING_MANUAL.md §13).

How it works at a glance
------------------------
1. The browser (templates/index.html) sends the input to the /screen endpoint.
2. dispatch_input() decides whether it's a website or a YouTube channel.
3. Websites go through screen_url(); channels go through youtube_api.screen_channel().
4. The result (tagged with "type") is returned as JSON and rendered in the UI.

Run it with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.

See OPERATING_MANUAL.md for a full developer walkthrough.
"""

import re
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

# Load environment variables from the .env file that sits NEXT TO this file
# (e.g. YOUTUBE_API_KEY). Using an explicit path based on __file__ means the
# key is found no matter which directory you launch the app from. Safe to call
# when no .env exists.
load_dotenv(Path(__file__).with_name(".env"))

import youtube_api
from summarizer import extract_visible_text, summarize_text

app = Flask(__name__)

# A normal browser User-Agent so sites are less likely to block us.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# How long to wait (seconds) before giving up on a slow site.
REQUEST_TIMEOUT = 12


# ---------------------------------------------------------------------------
# Step 1: Normalize and validate the URL the user typed.
# ---------------------------------------------------------------------------
def normalize_url(raw_url: str) -> str:
    """Add a scheme if the user left it off (e.g. 'example.com')."""
    url = (raw_url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


def is_valid_url(url: str) -> bool:
    """A light sanity check that we have a scheme and a host."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


# ---------------------------------------------------------------------------
# Step 2: Download the page.
# ---------------------------------------------------------------------------
def fetch_page(url: str):
    """Return (html_text, final_url). Raises requests exceptions on failure."""
    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text, response.url


# ---------------------------------------------------------------------------
# Step 3: Pull structured details out of the HTML.
# ---------------------------------------------------------------------------
def _first_match(pattern: str, html: str) -> str:
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return unescape(match.group(1)).strip() if match else ""


def extract_details(html: str) -> dict:
    """Extract the page title and meta/Open Graph description."""
    title = _first_match(r"<title[^>]*>(.*?)</title>", html)

    # Standard meta description (attributes can appear in either order).
    description = _first_match(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
    ) or _first_match(
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        html,
    )

    # Fall back to the Open Graph description used by social previews.
    if not description:
        description = _first_match(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
            html,
        )

    return {"title": title, "description": description}


# Note: the shared text helpers extract_visible_text() and summarize_text()
# live in summarizer.py (imported above) so the YouTube feature can reuse them.


# ---------------------------------------------------------------------------
# Step 4: Orchestrate everything for a single website URL.
# ---------------------------------------------------------------------------
def screen_url(raw_url: str) -> dict:
    """Run the full pipeline and return a result dict for the UI."""
    url = normalize_url(raw_url)
    if not is_valid_url(url):
        return {"ok": False, "error": "Please enter a valid website URL."}

    try:
        html, final_url = fetch_page(url)
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "The site took too long to respond."}
    except requests.exceptions.SSLError:
        return {"ok": False, "error": "There was an SSL/security problem reaching that site."}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Could not connect to that site. Check the URL and try again."}
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        return {"ok": False, "error": f"The site returned an error (HTTP {code})."}
    except requests.exceptions.RequestException:
        return {"ok": False, "error": "Something went wrong fetching that page."}

    details = extract_details(html)
    visible_text = extract_visible_text(html)
    summary = summarize_text(visible_text)

    # Choose the best available short description for the UI.
    description = details["description"] or summary or "No description available."

    return {
        "ok": True,
        "type": "website",
        "url": final_url,
        "domain": urlparse(final_url).netloc,
        "title": details["title"] or "(no page title found)",
        "description": description,
        "summary": summary or "Not enough readable text on the page to summarize.",
    }


# ---------------------------------------------------------------------------
# Step 5: Decide whether the input is a website or a YouTube channel.
# ---------------------------------------------------------------------------
def dispatch_input(raw: str) -> dict:
    """Route the user's input to the right handler and return a result dict."""
    if not (raw or "").strip():
        return {"ok": False, "type": "unknown",
                "error": "Please enter a website URL or a YouTube channel."}
    if youtube_api.looks_like_youtube(raw):
        return youtube_api.screen_channel(raw)
    return screen_url(raw)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the single-page UI."""
    return render_template("index.html")


@app.route("/screen", methods=["POST"])
def screen():
    """Accept {"url": "..."} JSON (a website URL or YouTube channel) and return JSON."""
    data = request.get_json(silent=True) or {}
    result = dispatch_input(data.get("url", ""))
    return jsonify(result)


if __name__ == "__main__":
    # debug=True gives auto-reload + helpful errors while developing.
    app.run(host="127.0.0.1", port=5000, debug=True)
