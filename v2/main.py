"""
Book Generator v2 — Entry point.

Usage:
    python main.py                          # interactive mode
    python main.py --config path/to/config.yaml  # custom config
    python main.py --input book_spec.json   # from JSON file
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional


def ask_user() -> dict:
    """Interactive prompt to collect book configuration from the user."""
    print()
    print("=" * 72)
    print("  Book Generator v2 — Interactive Setup")
    print("=" * 72)
    print()

    print("  What topic should the book be written on?")
    topic = input("  > ").strip()
    if not topic:
        topic = "The inner science of conscious living"
        print(f"  Using default topic: {topic}")
    print()

    title = input(f"  Book title [{topic}]: ").strip()
    if not title:
        title = topic
        print(f"  Using topic as title: {title}")

    subtitle = input("  Subtitle (optional, press Enter to skip): ").strip() or None

    author = input("  Author name: ").strip()
    if not author:
        author = "Anonymous"
        print(f"  Using default: {author}")

    num_chapters_str = input("  Number of chapters (3-20) [10]: ").strip()
    num_chapters = int(num_chapters_str) if num_chapters_str else 10

    words_str = input("  Target words per chapter (1000-8000) [2500]: ").strip()
    words_per_chapter = int(words_str) if words_str else 2500

    pov = input("  Point of view (e.g. 'first person', 'second person', 'third person') [first person]: ").strip()
    if not pov:
        pov = "first person"

    tone = input("  Tone (e.g. 'conversational', 'academic', 'spiritual') [spiritual-conversational]: ").strip()
    if not tone:
        tone = "spiritual-conversational"

    reading_level = input("  Reading level (e.g. 'casual', 'intermediate', 'scholarly') [intermediate]: ").strip()
    if not reading_level:
        reading_level = "intermediate"

    language = input("  Language [English]: ").strip() or "English"

    print()
    print("  Enter the book synopsis (2-3 sentences minimum).")
    print("  Press Enter twice when done:")
    synopsis_lines = []
    while True:
        line = input("  > ")
        if not line and synopsis_lines:
            break
        synopsis_lines.append(line)
    synopsis = "\n".join(synopsis_lines).strip()
    if not synopsis:
        synopsis = "An exploration of consciousness and inner transformation."

    themes_str = input("  Key themes (comma-separated): ").strip()
    themes = [t.strip() for t in themes_str.split(",") if t.strip()] if themes_str else ["awareness"]

    target_audience = input("  Target audience: ").strip()
    if not target_audience:
        target_audience = "General readers interested in personal growth"

    refs_str = input("  Reference sources (comma-separated URLs/paths, or Enter to skip): ").strip()
    reference_sources = [r.strip() for r in refs_str.split(",") if r.strip()] if refs_str else []

    print()
    return {
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "num_chapters": num_chapters,
        "words_per_chapter": words_per_chapter,
        "pov": pov,
        "tone": tone,
        "reading_level": reading_level,
        "language": language,
        "synopsis": synopsis,
        "themes": themes,
        "target_audience": target_audience,
        "reference_sources": reference_sources,
    }


async def async_main(
    input_data: Optional[dict] = None,
    config_path: Optional[str] = None,
) -> None:
    from workflow import run_pipeline

    raw_input = input_data or ask_user()

    try:
        state = await run_pipeline(
            raw_input=raw_input,
            mcp_tools=None,  # MCP tools will be hooked up separately
            config_path=config_path,
        )
    except Exception as exc:
        print(f"\n  Pipeline failed: {exc}")
        raise


def main() -> None:
    config_path: Optional[str] = None
    input_data: Optional[dict] = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
        elif args[i] == "--input" and i + 1 < len(args):
            input_path = Path(args[i + 1])
            input_data = json.loads(input_path.read_text(encoding="utf-8"))
            i += 2
        else:
            i += 1

    asyncio.run(async_main(input_data=input_data, config_path=config_path))


if __name__ == "__main__":
    main()
