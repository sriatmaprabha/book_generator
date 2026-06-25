"""
Full book generation — generates a book in the voice of
The SPH Bhagwan Sri Nithyananda Paramashivam.

Usage:
    python full_run.py                            # interactive prompts
    python full_run.py --topic "Shiva Consciousness"
    python full_run.py --topic "..." --chapters 10
    python full_run.py --topic "..." --chapters 12 --words 3000
"""

import asyncio
import sys


def _parse_args() -> dict:
    """Parse optional CLI args: --topic, --chapters, --words."""
    args = sys.argv[1:]
    result = {}
    i = 0
    while i < len(args):
        if args[i] in ("--topic", "-t") and i + 1 < len(args):
            result["topic"] = args[i + 1]
            i += 2
        elif args[i] in ("--chapters", "-c") and i + 1 < len(args):
            result["chapters"] = int(args[i + 1])
            i += 2
        elif args[i] in ("--words", "-w") and i + 1 < len(args):
            result["words"] = int(args[i + 1])
            i += 2
        else:
            i += 1
    return result


def _estimate_pages(num_chapters: int, words_per_chapter: int) -> tuple[int, int]:
    """Return (low, high) page estimate for the finished .docx."""
    # ~300 words/page at Palatino 11pt with standard margins
    # Add ~900 words for foreword + benediction + TOC/title page
    total_words = (num_chapters * words_per_chapter) + 900
    low = round(total_words / 320)
    high = round(total_words / 280)
    return low, high


async def main():
    from workflow import run_pipeline

    cli = _parse_args()

    print()
    print("=" * 72)
    print("  Book Generator v2 — Full Run")
    print("=" * 72)
    print()

    # Topic
    topic = cli.get("topic", "").strip()
    if not topic:
        topic = input("  What topic should the book be written on?\n  > ").strip()
    if not topic:
        topic = "The inner science of witnessing consciousness"
        print(f"  Using default: {topic}")

    # Chapter count
    num_chapters = cli.get("chapters", 0)
    if not num_chapters:
        ch_str = input("  Number of chapters (3-20) [7]: ").strip()
        num_chapters = int(ch_str) if ch_str else 7
    num_chapters = max(3, min(20, num_chapters))

    # Words per chapter
    words_per_chapter = cli.get("words", 0)
    if not words_per_chapter:
        w_str = input("  Target words per chapter (1000-8000) [2500]: ").strip()
        words_per_chapter = int(w_str) if w_str else 2500
    words_per_chapter = max(1000, min(8000, words_per_chapter))

    # Page estimate
    pg_low, pg_high = _estimate_pages(num_chapters, words_per_chapter)
    total_words_est = num_chapters * words_per_chapter + 900
    print()
    print(f"  Topic      : {topic}")
    print(f"  Chapters   : {num_chapters}")
    print(f"  Words/ch   : {words_per_chapter:,}")
    print(f"  Est. words : ~{total_words_est:,}")
    print(f"  Est. pages : ~{pg_low}–{pg_high} pages (Word doc, Palatino 11pt)")
    print()

    book_input = {
        "title": topic,
        "subtitle": f"Discovering the Science of {topic} Through Living Enlightenment",
        "author": "The SPH Bhagwan Sri Nithyananda Paramashivam",
        "num_chapters": num_chapters,
        "words_per_chapter": words_per_chapter,
        "pov": "first person",
        "tone": "spiritual-conversational",
        "reading_level": "intermediate",
        "language": "English",
        "synopsis": (
            f"This book is a direct transmission from The SPH Nithyananda Paramashivam "
            f"exploring '{topic}' through the lens of Living Enlightenment. "
            "Each chapter opens with an immersive story — varying between short parables, "
            "Swamiji's autobiographical experiences, devotee encounters, and real-life incidents "
            "— in the authentic Living Enlightenment storytelling style. The teaching unfolds "
            "anchored in exact Sanskrit shastric verses from the Vedas, Agamas, and Upanishads "
            "with faithful translations. Each chapter offers a hands-on spiritual practice "
            "(sadhana) and closes with a bridge that carries the reader deeper into the next "
            "insight. The book draws from authentic Vedic-Agamic sources and the living "
            "tradition of Sanatana Hindu Dharma to illuminate the timeless science behind the topic."
        ),
        "themes": [
            topic,
            "Paramashiva as inner reality",
            "consciousness",
            "living enlightenment",
            "Sanatana Hindu Dharma",
            "shastric wisdom",
            "spiritual practice",
        ],
        "target_audience": "Spiritual seekers, Hindu devotees, and meditators",
        "reference_sources": [
            "https://jnanalaya.kailasa.ai/mcp",
            "https://jnanalaya.nithyananda.ai/mcp",
        ],
        "section_template": [
            "opening_story",
            "teaching",
            "practical_exercise",
            "humor",
            "closing_bridge",
        ],
        "include_foreword": True,
        "include_benediction": True,
        "include_toc": True,
    }

    state = await run_pipeline(raw_input=book_input, skip_mcp=False)

    print(f"\n  Final output: {state.docx_path}")
    total = sum(c.final_word_count for c in state.edited.values())
    foreword_wc = len(getattr(state, "_foreword", "").split())
    bene_wc = len(getattr(state, "_benediction", "").split())
    grand_total = total + foreword_wc + bene_wc
    actual_low = round(grand_total / 320)
    actual_high = round(grand_total / 280)
    print(f"  Total words: {grand_total:,}  (chapters: {total:,} | foreword: {foreword_wc} | benediction: {bene_wc})")
    print(f"  Est. pages : ~{actual_low}–{actual_high} pages")
    print(f"  Errors     : {state.status['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
