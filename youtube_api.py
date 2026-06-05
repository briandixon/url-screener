"""
youtube_api.py
==============

YouTube channel lookup (added in v1.1.0).

Given a YouTube channel name, @handle, or channel URL, this module resolves the
channel via the official **YouTube Data API v3** and returns an overview plus
links/creator info, including a short auto-summary of the channel's description.

Why the official API: YouTube pages are heavily JavaScript-rendered and block
scraping, so the Data API is the only dependable way to get channel details.

Configuration
-------------
Set an API key in the environment variable ``YOUTUBE_API_KEY`` (app.py loads a
local ``.env`` file automatically, so you can put it there). See OPERATING_MANUAL.md
§13 for step-by-step instructions on creating a free key.

Public function:
    screen_channel(raw_input) -> dict   The full pipeline for the UI.
"""

import os
import re
from urllib.parse import unquote

import requests

from summarizer import summarize_text

# Base endpoint for all Data API v3 calls.
API_BASE = "https://www.googleapis.com/youtube/v3"
REQUEST_TIMEOUT = 12


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def get_api_key() -> str:
    """Read the YouTube Data API key from the environment (may be empty)."""
    return (os.environ.get("YOUTUBE_API_KEY") or "").strip()


# ---------------------------------------------------------------------------
# Step 1: Decide what the user typed and how to resolve it.
# ---------------------------------------------------------------------------
def looks_like_youtube(text: str) -> bool:
    """True if the input should be treated as a YouTube channel rather than a website."""
    text = (text or "").strip()
    if not text:
        return False
    if re.search(r"\b(youtube\.com|youtu\.be)\b", text, re.IGNORECASE):
        return True
    if text.startswith("@"):  # an @handle
        return True
    # A bare word / phrase with no dot-TLD and no scheme is treated as a
    # channel name to search for (e.g. "Veritasium", "Kurzgesagt").
    looks_like_domain = re.match(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(/|$|\?)",
                                 text, re.IGNORECASE)
    return not looks_like_domain


def _parse_youtube_url(text: str):
    """Return ('id'|'handle'|'user'|'search', value) extracted from a YouTube URL."""
    m = re.search(r"youtube\.com/channel/([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if m:
        return ("id", m.group(1))
    m = re.search(r"youtube\.com/@([A-Za-z0-9_.\-]+)", text, re.IGNORECASE)
    if m:
        return ("handle", "@" + m.group(1))
    m = re.search(r"youtube\.com/user/([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if m:
        return ("user", m.group(1))
    m = re.search(r"youtube\.com/c/([A-Za-z0-9_%\-]+)", text, re.IGNORECASE)
    if m:
        return ("search", unquote(m.group(1)))
    return None


# ---------------------------------------------------------------------------
# Step 2: Thin wrappers over the Data API endpoints.
# ---------------------------------------------------------------------------
def _api_get(endpoint: str, params: dict, api_key: str) -> dict:
    """GET a Data API endpoint and return parsed JSON (raises on HTTP error)."""
    params = dict(params)
    params["key"] = api_key
    response = requests.get(f"{API_BASE}/{endpoint}", params=params,
                            timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _channel_id_by_handle(handle: str, api_key: str):
    data = _api_get("channels", {"part": "id", "forHandle": handle}, api_key)
    items = data.get("items", [])
    return items[0]["id"] if items else None


def _channel_id_by_username(username: str, api_key: str):
    data = _api_get("channels", {"part": "id", "forUsername": username}, api_key)
    items = data.get("items", [])
    return items[0]["id"] if items else None


def _channel_id_by_search(query: str, api_key: str):
    data = _api_get("search", {"part": "snippet", "type": "channel",
                               "q": query, "maxResults": 1}, api_key)
    items = data.get("items", [])
    return items[0]["id"]["channelId"] if items else None


def resolve_channel_id(raw: str, api_key: str):
    """Turn whatever the user typed into a concrete channel id (or None)."""
    raw = raw.strip()
    if re.search(r"youtube\.com|youtu\.be", raw, re.IGNORECASE):
        parsed = _parse_youtube_url(raw)
        if parsed:
            kind, value = parsed
            if kind == "id":
                return value
            if kind == "handle":
                return _channel_id_by_handle(value, api_key)
            if kind == "user":
                return _channel_id_by_username(value, api_key)
            if kind == "search":
                return _channel_id_by_search(value, api_key)
        return _channel_id_by_search(raw, api_key)  # unknown URL shape
    if raw.startswith("@"):
        return _channel_id_by_handle(raw, api_key)
    return _channel_id_by_search(raw, api_key)  # treat as a channel name


# ---------------------------------------------------------------------------
# Step 3: Fetch the channel and shape the result for the UI.
# ---------------------------------------------------------------------------
def _fetch_channel(channel_id: str, api_key: str):
    data = _api_get("channels",
                    {"part": "snippet,brandingSettings", "id": channel_id},
                    api_key)
    items = data.get("items", [])
    return items[0] if items else None


def _thumbnail(snippet: dict) -> str:
    thumbs = snippet.get("thumbnails", {})
    for size in ("high", "medium", "default"):
        if thumbs.get(size, {}).get("url"):
            return thumbs[size]["url"]
    return ""


def build_result(channel: dict) -> dict:
    """Map a raw API channel object to the dict the front-end renders."""
    snippet = channel.get("snippet", {})
    branding = channel.get("brandingSettings", {})

    channel_id = channel.get("id", "")
    title = snippet.get("title", "(unknown channel)")
    description = snippet.get("description", "").strip()
    custom_url = snippet.get("customUrl", "")  # e.g. "@veritasium"
    country = snippet.get("country", "")
    published = (snippet.get("publishedAt", "") or "")[:10]  # YYYY-MM-DD

    # Prefer the handle URL if we have one, else the canonical channel URL.
    if custom_url:
        handle = custom_url if custom_url.startswith("@") else "@" + custom_url
        channel_url = f"https://www.youtube.com/{handle}"
    else:
        handle = ""
        channel_url = f"https://www.youtube.com/channel/{channel_id}"

    banner = branding.get("image", {}).get("bannerExternalUrl", "")

    summary = summarize_text(description) if description else ""

    return {
        "ok": True,
        "type": "youtube",
        "title": title,
        "handle": handle,
        "description": description or "(this channel has no description)",
        "summary": summary or "Not enough description text to summarize.",
        "channel_url": channel_url,
        "avatar": _thumbnail(snippet),
        "banner": banner,
        "country": country,
        "published": published,
    }


# ---------------------------------------------------------------------------
# Step 4: Orchestrate everything for one lookup.
# ---------------------------------------------------------------------------
def screen_channel(raw: str) -> dict:
    """Full pipeline: validate config, resolve the channel, return a result dict."""
    api_key = get_api_key()
    if not api_key:
        return {
            "ok": False,
            "type": "youtube",
            "error": ("YouTube lookups need a free API key. Set YOUTUBE_API_KEY "
                      "in a .env file, then restart the app. See OPERATING_MANUAL.md "
                      "§13 for the 2-minute setup."),
        }

    try:
        channel_id = resolve_channel_id(raw, api_key)
        if not channel_id:
            return {"ok": False, "type": "youtube",
                    "error": f"No YouTube channel found for “{raw}”."}

        channel = _fetch_channel(channel_id, api_key)
        if not channel:
            return {"ok": False, "type": "youtube",
                    "error": "Found the channel id but could not load its details."}

        return build_result(channel)

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 403:
            return {"ok": False, "type": "youtube",
                    "error": ("YouTube API rejected the request (HTTP 403). The key "
                              "may be invalid, restricted, or out of daily quota.")}
        return {"ok": False, "type": "youtube",
                "error": f"YouTube API error (HTTP {status})."}
    except requests.exceptions.Timeout:
        return {"ok": False, "type": "youtube",
                "error": "The YouTube API took too long to respond."}
    except requests.exceptions.RequestException:
        return {"ok": False, "type": "youtube",
                "error": "Could not reach the YouTube API."}
