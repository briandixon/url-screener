"""
URL Screener
============

A small Flask web app that takes a website URL from the user, fetches the page,
and returns a brief description plus an auto-generated summary built entirely
from the page's own content (no external AI API or API key required).

How it works at a glance
------------------------
1. The browser (templates/index.html) sends the URL to the /screen endpoint.
2. fetch_page() downloads the HTML.
3. extract_details() pulls the title and meta description out of the markup.
4. summarize_text() builds a short extractive summary from the visible text.
5. The result is returned as JSON and rendered in the UI.

Run it with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.

See OPERATING_MANUAL.md for a full developer walkthrough.
"""

import re
from html import unescape
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request

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

# Very common English words we don't want cluttering the summary scoring.
STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "her", "was", "one", "our", "out", "day", "had", "has", "his", "how",
    "man", "new", "now", "old", "see", "two", "way", "who", "boy", "did",
    "its", "let", "put", "say", "she", "too", "use", "this", "that", "with",
    "from", "they", "will", "would", "there", "their", "what", "about",
    "which", "when", "your", "have", "more", "here", "than", "then", "them",
    "these", "some", "into", "only", "other", "such", "also", "been", "were",
}


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


# ---------------------------------------------------------------------------
# Step 4: Reduce the page to clean, readable text.
# ---------------------------------------------------------------------------
def extract_visible_text(html: str) -> str:
    """Strip scripts/styles/tags and return collapsed visible text."""
    # Remove the parts of the page that aren't human-readable content.
    html = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ",
                  html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    # Drop all remaining tags, then decode HTML entities.
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    # Collapse runs of whitespace into single spaces.
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list:
    """A simple sentence splitter good enough for summarization."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 0]


# ---------------------------------------------------------------------------
# Step 5: Build an extractive summary by scoring sentences.
# ---------------------------------------------------------------------------
def summarize_text(text: str, max_sentences: int = 3) -> str:
    """
    Pick the most representative sentences using simple word-frequency scoring.

    The idea: words that appear often across the page are likely important, so
    sentences containing many of those words are good summary candidates. We
    keep the chosen sentences in their original reading order.
    """
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    # Count how often each meaningful word appears.
    word_frequencies = {}
    for word in re.findall(r"[a-zA-Z]{3,}", text.lower()):
        if word in STOP_WORDS:
            continue
        word_frequencies[word] = word_frequencies.get(word, 0) + 1

    if not word_frequencies:
        return " ".join(sentences[:max_sentences])

    peak = max(word_frequencies.values())

    # Score each sentence; normalize a bit by length to avoid favoring only
    # the longest sentences. Only the first ~30 sentences are considered so
    # we focus on the main content near the top of the page.
    scored = []
    for index, sentence in enumerate(sentences[:30]):
        words = re.findall(r"[a-zA-Z]{3,}", sentence.lower())
        if not (4 <= len(words) <= 60):
            continue
        score = sum(word_frequencies.get(w, 0) for w in words) / (peak * len(words))
        scored.append((score, index, sentence))

    if not scored:
        return " ".join(sentences[:max_sentences])

    # Take the top-scoring sentences, then restore original order.
    top = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    top_in_order = sorted(top, key=lambda item: item[1])
    return " ".join(sentence for _, _, sentence in top_in_order)


# ---------------------------------------------------------------------------
# Step 6: Orchestrate everything for a single URL.
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
        "url": final_url,
        "domain": urlparse(final_url).netloc,
        "title": details["title"] or "(no page title found)",
        "description": description,
        "summary": summary or "Not enough readable text on the page to summarize.",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the single-page UI."""
    return render_template("index.html")


@app.route("/screen", methods=["POST"])
def screen():
    """Accept {"url": "..."} JSON and return the screening result as JSON."""
    data = request.get_json(silent=True) or {}
    result = screen_url(data.get("url", ""))
    return jsonify(result)


if __name__ == "__main__":
    # debug=True gives auto-reload + helpful errors while developing.
    app.run(host="127.0.0.1", port=5000, debug=True)
