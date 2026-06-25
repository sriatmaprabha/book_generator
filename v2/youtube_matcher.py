"""
YouTube channel video matcher for Book Generator v2.

Searches the @SriNithyananda YouTube channel for videos matching
each chapter's topics. Returns SourceLink objects for QR code generation.

No LLM used — pure YouTube Data API v3 calls.
Requires YOUTUBE_API_KEY in environment / .env file.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

from models import SourceLink

# ── Constants ──────────────────────────────────────────────────────────────

CHANNEL_HANDLE   = "SriNithyananda"
CHANNEL_URL      = "https://www.youtube.com/@SriNithyananda"
YT_API_BASE      = "https://www.googleapis.com/youtube/v3"
RESULTS_PER_CHAPTER = 5    # max videos to return per chapter
REQUEST_TIMEOUT  = 15      # seconds

# Cache file so we look up the channel ID only once per machine
_CACHE_FILE = Path(__file__).parent / ".youtube_channel_id_cache.json"


# ── Low-level API helpers ───────────────────────────────────────────────────

def _get(url: str, params: dict) -> dict:
    """Make a GET request to the YouTube Data API and return parsed JSON."""
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        full_url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_channel_id_cache() -> Optional[str]:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            return data.get("channel_id")
    except Exception:
        pass
    return None


def _save_channel_id_cache(channel_id: str) -> None:
    try:
        _CACHE_FILE.write_text(json.dumps({"channel_id": channel_id, "handle": CHANNEL_HANDLE}))
    except Exception:
        pass


# ── Channel ID lookup ───────────────────────────────────────────────────────

def get_channel_id(api_key: str) -> str:
    """
    Resolve @SriNithyananda to a YouTube channel ID.
    Result is cached locally so this only hits the API once.
    """
    cached = _load_channel_id_cache()
    if cached:
        return cached

    print(f"  YouTube: resolving channel ID for @{CHANNEL_HANDLE}...")
    try:
        data = _get(f"{YT_API_BASE}/channels", {
            "part":      "id",
            "forHandle": CHANNEL_HANDLE,
            "key":       api_key,
        })
        items = data.get("items", [])
        if not items:
            raise RuntimeError(
                f"YouTube API returned no channel for handle @{CHANNEL_HANDLE}. "
                "Check that the channel is active and the API key has YouTube Data API v3 enabled."
            )
        channel_id = items[0]["id"]
        _save_channel_id_cache(channel_id)
        print(f"  YouTube: channel ID resolved → {channel_id}")
        return channel_id

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"YouTube API error resolving channel ID (HTTP {exc.code}): {body[:300]}"
        ) from exc


# ── Video search ────────────────────────────────────────────────────────────

def _build_query(teaching_points: List[str], title: str) -> str:
    """
    Build a compact search query from chapter teaching_points + title.
    Keeps it under ~100 chars so the API doesn't truncate it.
    """
    # Take the 3 most important teaching points + the chapter title keywords
    keywords: List[str] = []
    for tp in teaching_points[:3]:
        # Extract the first 2-3 words of each teaching point
        words = re.sub(r"[^a-zA-Z\s]", "", tp).split()[:3]
        keywords.extend(words)

    # Add the most distinctive words from the chapter title
    title_words = re.sub(r"[^a-zA-Z\s]", "", title).split()
    # Skip common stop words
    stop = {"the", "a", "an", "of", "in", "to", "and", "is", "are", "for", "with", "this", "that"}
    title_words = [w for w in title_words if w.lower() not in stop][:3]
    keywords.extend(title_words)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw.lower() not in seen and len(kw) > 2:
            seen.add(kw.lower())
            unique.append(kw)

    query = " ".join(unique[:8])  # YouTube search query cap
    return query or title


def _relevance_score(video: dict, teaching_points: List[str], chapter_title: str) -> float:
    """
    Score a video result by keyword overlap with chapter content.
    Higher = more relevant.
    """
    snippet = video.get("snippet", {})
    haystack = (
        (snippet.get("title", "") + " " + snippet.get("description", "")).lower()
    )

    # Keywords to match against
    keywords = set()
    for tp in teaching_points:
        for word in re.sub(r"[^a-zA-Z\s]", "", tp).lower().split():
            if len(word) > 3:
                keywords.add(word)
    for word in re.sub(r"[^a-zA-Z\s]", "", chapter_title).lower().split():
        if len(word) > 3:
            keywords.add(word)

    if not keywords:
        return 0.0

    matches = sum(1 for kw in keywords if kw in haystack)
    return matches / len(keywords)


def search_channel_videos(
    channel_id: str,
    api_key: str,
    chapter_number: int,
    chapter_title: str,
    teaching_points: List[str],
    max_results: int = RESULTS_PER_CHAPTER,
) -> List[SourceLink]:
    """
    Search the @SriNithyananda channel for videos matching a chapter's topics.
    Returns up to max_results SourceLink objects sorted by relevance.
    """
    query = _build_query(teaching_points, chapter_title)

    try:
        data = _get(f"{YT_API_BASE}/search", {
            "part":       "snippet",
            "channelId":  channel_id,
            "q":          query,
            "type":       "video",
            "maxResults": min(max_results * 2, 20),  # fetch extra, then score + trim
            "order":      "relevance",
            "key":        api_key,
        })
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"  YouTube: search failed for Ch{chapter_number} (HTTP {exc.code}): {body[:200]}")
        return []
    except Exception as exc:
        print(f"  YouTube: search error for Ch{chapter_number}: {exc}")
        return []

    items = data.get("items", [])
    if not items:
        return []

    # Score each result
    scored = []
    for item in items:
        snippet  = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId", "")
        if not video_id:
            continue
        score = _relevance_score(item, teaching_points, chapter_title)
        scored.append((score, item))

    # Sort by relevance descending
    scored.sort(key=lambda x: x[0], reverse=True)

    links: List[SourceLink] = []
    for score, item in scored[:max_results]:
        snippet  = item.get("snippet", {})
        video_id = item["id"]["videoId"]
        title    = snippet.get("title", "Untitled")
        raw_date = snippet.get("publishedAt", "")
        # Format: "2019-03-14T10:30:00Z" → "14 Mar 2019"
        date_str = ""
        if raw_date:
            try:
                from datetime import datetime
                dt = datetime.strptime(raw_date[:10], "%Y-%m-%d")
                date_str = dt.strftime("%-d %b %Y")
            except Exception:
                date_str = raw_date[:10]

        links.append(SourceLink(
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            date=date_str,
            chapter_number=chapter_number,
        ))

    return links


# ── Main entry point (called by workflow) ──────────────────────────────────

def match_videos_for_chapters(
    chapters_data: List[dict],
    api_key: str,
    pause_between: float = 0.5,
) -> List[SourceLink]:
    """
    Match YouTube videos for a list of chapters.

    Args:
        chapters_data: List of dicts with keys:
                       chapter_number, title, teaching_points
        api_key:       YouTube Data API v3 key
        pause_between: Seconds to wait between API calls (rate limiting)

    Returns:
        All matched SourceLink objects across all chapters.
    """
    channel_id = get_channel_id(api_key)
    all_links: List[SourceLink] = []

    for ch in chapters_data:
        ch_num    = ch["chapter_number"]
        title     = ch["title"]
        points    = ch.get("teaching_points", [])

        links = search_channel_videos(
            channel_id=channel_id,
            api_key=api_key,
            chapter_number=ch_num,
            chapter_title=title,
            teaching_points=points,
        )
        all_links.extend(links)
        print(f"  YouTube Ch{ch_num}: '{title[:40]}' → {len(links)} video(s) matched")

        if pause_between > 0:
            time.sleep(pause_between)

    return all_links
