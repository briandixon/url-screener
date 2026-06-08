"""
tagger.py
=========

Local, dependency-free content tagging (added in v1.3.0).

Given a piece of content (a web page's text, or a YouTube channel's
description) plus a few hints (domain, title, description), this module assigns
a handful of short, generic category tags such as "Sports", "News", or
"Technology".

Design philosophy (same as summarizer.py)
-----------------------------------------
Tagging runs **fully locally** with no API key, no external service, and no
extra dependencies. It is transparent and deterministic: the same input always
yields the same tags. There are two complementary signals:

  1. DOMAIN_HINTS  - a small curated map of well-known domains to high-confidence
     tags (e.g. espn.com -> Sports + Media). These are strong, exact signals.
  2. CATEGORY_KEYWORDS - for everything else, score each category by how often
     its signal words appear in the content, then keep the strongest categories.

The two signals are merged: domain hints are always included, and the best
keyword-scored categories fill the rest, up to MAX_TAGS.

Public function:
    generate_tags(text, domain="", title="", description="") -> list[str]
"""

import re
from urllib.parse import urlparse

# At most this many tags per result, so cards stay readable.
MAX_TAGS = 4

# A keyword must clear this score to be considered a real signal (filters out
# a single incidental keyword match).
MIN_KEYWORD_SCORE = 2


# ---------------------------------------------------------------------------
# Curated taxonomy: category label -> signal keywords.
# ---------------------------------------------------------------------------
# Keywords are matched as whole words, case-insensitively. Keep them generic
# and high-signal; avoid words common to many topics. Order here also breaks
# ties (earlier categories win when scores are equal), so list broad/common
# categories sensibly.
CATEGORY_KEYWORDS = {
    "News": [
        "news", "breaking", "headlines", "reporter", "journalism", "newsroom",
        "coverage", "politics", "election", "world", "reuters", "editorial",
    ],
    "Sports": [
        "sports", "sport", "football", "soccer", "basketball", "baseball",
        "hockey", "tennis", "golf", "nba", "nfl", "mlb", "league", "playoffs",
        "athlete", "match", "tournament", "scores", "espn",
    ],
    "Media": [
        "media", "video", "videos", "streaming", "stream", "watch", "channel",
        "broadcast", "network", "tv", "podcast", "episode", "live",
    ],
    "Technology": [
        "technology", "tech", "software", "hardware", "app", "apps", "developer",
        "programming", "code", "computing", "cloud", "data", "digital", "ai",
        "gadget", "devices", "startup",
    ],
    "Finance": [
        "finance", "financial", "money", "market", "markets", "stock", "stocks",
        "investing", "investment", "economy", "economic", "trading", "banking",
        "bank", "crypto", "business", "earnings",
    ],
    "Shopping": [
        "shop", "shopping", "store", "buy", "cart", "checkout", "price",
        "deals", "sale", "product", "products", "order", "shipping", "retail",
    ],
    "Entertainment": [
        "entertainment", "movie", "movies", "film", "music", "celebrity",
        "show", "shows", "trailer", "concert", "actor", "hollywood",
    ],
    "Gaming": [
        "gaming", "game", "games", "gamer", "playstation", "xbox", "nintendo",
        "esports", "console", "multiplayer", "twitch",
    ],
    "Education": [
        "education", "learn", "learning", "course", "courses", "tutorial",
        "lesson", "lessons", "school", "university", "students", "teaching",
        "academy",
    ],
    "Science": [
        "science", "scientific", "research", "physics", "chemistry", "biology",
        "space", "astronomy", "experiment", "discovery", "scientists",
    ],
    "Health": [
        "health", "medical", "medicine", "wellness", "fitness", "doctor",
        "hospital", "nutrition", "mental", "healthcare", "patient",
    ],
    "Travel": [
        "travel", "flight", "flights", "hotel", "hotels", "vacation", "trip",
        "destination", "tourism", "booking", "airline",
    ],
    "Food": [
        "food", "recipe", "recipes", "cooking", "restaurant", "kitchen", "meal",
        "cuisine", "dining", "chef", "baking",
    ],
    "Government": [
        "government", "policy", "federal", "agency", "official", "congress",
        "senate", "department", "regulation", "public",
    ],
}


# ---------------------------------------------------------------------------
# Known domains -> high-confidence tags. The key is matched against the
# registered domain (e.g. "espn.com" matches "www.espn.com" and "espn.com").
# ---------------------------------------------------------------------------
DOMAIN_HINTS = {
    "espn.com": ["Sports", "Media"],
    "nfl.com": ["Sports"],
    "nba.com": ["Sports"],
    "mlb.com": ["Sports"],
    "wsj.com": ["News", "Finance"],
    "nytimes.com": ["News"],
    "bbc.com": ["News", "Media"],
    "bbc.co.uk": ["News", "Media"],
    "cnn.com": ["News", "Media"],
    "reuters.com": ["News"],
    "bloomberg.com": ["Finance", "News"],
    "youtube.com": ["Media"],
    "netflix.com": ["Entertainment", "Media"],
    "spotify.com": ["Music", "Media"],
    "amazon.com": ["Shopping"],
    "ebay.com": ["Shopping"],
    "etsy.com": ["Shopping"],
    "github.com": ["Technology"],
    "stackoverflow.com": ["Technology"],
    "techcrunch.com": ["Technology", "News"],
    "wikipedia.org": ["Education", "Reference"],
    "coursera.org": ["Education"],
    "khanacademy.org": ["Education"],
    "webmd.com": ["Health"],
    "steampowered.com": ["Gaming"],
    "twitch.tv": ["Gaming", "Media"],
    "tripadvisor.com": ["Travel"],
    "booking.com": ["Travel"],
}


def _registered_domain(domain: str) -> str:
    """Reduce a host like 'www.espn.com' to 'espn.com' for hint lookup."""
    host = (domain or "").strip().lower()
    if not host:
        return ""
    # If a full URL slipped in, pull just the host out.
    if "/" in host:
        host = urlparse(host if "://" in host else "//" + host).netloc
    host = host.split(":")[0]  # drop any port
    parts = host.split(".")
    # Keep the last two labels (good enough for the common .com/.org/etc cases
    # we hint on; multi-part TLDs like .co.uk are covered by explicit keys).
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _score_categories(content: str) -> dict:
    """Return {category: score} from whole-word keyword counts in `content`."""
    words = re.findall(r"[a-z]+", content.lower())
    if not words:
        return {}
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(counts.get(keyword, 0) for keyword in keywords)
        if score >= MIN_KEYWORD_SCORE:
            scores[category] = score
    return scores


def generate_tags(text: str, domain: str = "", title: str = "",
                  description: str = "") -> list:
    """
    Assign up to MAX_TAGS short category tags to a piece of content.

    Signals, in priority order:
      1. Exact known-domain hints (always included first).
      2. Keyword scoring across title + description + body text, with the
         title/description weighted more heavily since they are the most
         topical part of a page.

    Returns a de-duplicated, order-stable list of tag strings (possibly empty).
    """
    tags = []

    # 1. Domain hints come first and are the most trustworthy.
    for tag in DOMAIN_HINTS.get(_registered_domain(domain), []):
        if tag not in tags:
            tags.append(tag)

    # 2. Keyword scoring. Weight the title/description by repeating them, since
    #    those few words describe the page better than the bulk body text.
    emphasis = " ".join([title or "", description or ""])
    content = " ".join([emphasis, emphasis, text or ""])
    scores = _score_categories(content)

    # Highest score first; CATEGORY_KEYWORDS insertion order breaks ties so the
    # result is deterministic.
    ranked = sorted(scores, key=lambda cat: scores[cat], reverse=True)
    for category in ranked:
        if len(tags) >= MAX_TAGS:
            break
        if category not in tags:
            tags.append(category)

    return tags[:MAX_TAGS]
