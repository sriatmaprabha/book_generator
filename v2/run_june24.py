"""
Book generation seeded from the June 24, 2026 satsang:
"Parakaya Pravesha — The Technology of Consciousness Travel"

Usage:
    cd /Users/sriatmaprabha/Desktop/book_generator/v2
    python3 run_june24.py
    python3 run_june24.py --chapters 9
    python3 run_june24.py --chapters 7 --words 3000
"""

import asyncio
import sys
from pathlib import Path


def _parse_args() -> dict:
    args = sys.argv[1:]
    result = {}
    i = 0
    while i < len(args):
        if args[i] in ("--chapters", "-c") and i + 1 < len(args):
            result["chapters"] = int(args[i + 1])
            i += 2
        elif args[i] in ("--words", "-w") and i + 1 < len(args):
            result["words"] = int(args[i + 1])
            i += 2
        else:
            i += 1
    return result


def _estimate_pages(num_chapters: int, words_per_chapter: int) -> tuple:
    total_words = (num_chapters * words_per_chapter) + 900
    return round(total_words / 320), round(total_words / 280)


BOOK_SYNOPSIS = """\
This book is a direct transmission from The SPH Bhagwan Sri Nithyananda Paramashivam
revealing the complete science of Parakaya Pravesha — the ancient Vedic-Agamic technology
by which consciousness consciously travels between bodies, planes, dimensions, and simultaneous
lives. It is the ultimate answer to the deepest question of existence: why does this one world
feel so absolute, so final, so inescapable — and how can we step beyond that illusion?

The book opens by naming the great hoax: human consciousness has entered one particular reality
field — one set of memories, one identity, one body, one timeline — and mistaken it for the
total truth of existence. You are not local. You are not limited. Right now, multiple versions
of you are living, breathing, and deciding across different lokas, different dimensions,
different planes of existence simultaneously.

The teaching unfolds through the five Stabilizers — Memory, Identity, Attention, Time Sense,
and Relational Space — the five mechanisms that lock consciousness inside a single reality frame
and make it feel absolute. When these five reconfigure under Guru Kripa, consciousness is free
to perceive, interact with, and rewrite its parallel existences.

The heart of the book is the extraordinary story of Queen Leela from the Yoga Vasistha,
narrated by Brahmarishi Vashishta to Bhagwan Rama — a living demonstration of how time is
relative, space is non-absolute, identity is layered, and worlds are nested. Leela's journey
— guided at every step by Goddess Saraswati as the embodiment of Guru Tattva — is a precise
map of what the sincere seeker can access right now.

Anchored in Patanjali's Yoga Sutras (Bandha Karana Shaithilyat Paracharira Aveshaha),
the Yogavasistha (30,000+ verses), and direct Agamic revelation, each chapter offers both
the cosmic science and a hands-on sadhana for accessing one's parallel realities —
completing karmic patterns across timelines, updating capacities from higher-plane versions
of oneself, and manifesting a completely different life in the present.

The book closes with Swamiji's living initiation into Paramadvaita — the direct, non-dual
recognition that one is not one body, one name, one passport. One is the infinite focal point
of Paramashiva consciousness itself, playing Leela across the multiverse, eternally 16,
rooted in the ultimate truth beyond all stabilizers.
"""

BOOK_THEMES = [
    "Parakaya Pravesha — consciousness travel between bodies and planes",
    "Five stabilizers of reality: memory, identity, attention, time sense, relational space",
    "Queen Leela and the nested worlds of the Yoga Vasistha",
    "Paramadvaita — the non-dual state beyond single-reality imprisonment",
    "Guru Tattva as the bridge to higher planes of consciousness",
    "Sankalpa — the creative power of intention in forming and dissolving reality fields",
    "Time and space as relative, not absolute — thousands of years before modern science",
    "Parallel universes and simultaneous lives across different lokas",
    "Nirvikalpa Samadhi as the conscious suspension of the five stabilizers",
    "Living Enlightenment through direct experience rather than intellectual belief",
    "Rama's spiritual disillusionment and Vashishta's cosmic answer",
    "Sanatana Hindu Dharma as a lived science of consciousness, not theory",
]

# Chapter titles drawn directly from the satsang's structure and revelations.
# The Architect can refine these — providing them as seeds ensures the book
# stays tightly aligned to the June 24 discourse.
CHAPTER_TITLES = [
    # Preface
    "This World Is the Hoax",
    # Introduction
    "You Are Not Local",
    # Preliminary — Part I: The Prison of One Reality
    "The Five Locks That Keep You Here",
    "Memory, Identity, and the Story You Feed Every Day",
    # Main — Part II: The Map of Nested Worlds
    "Queen Leela's Journey Into the Akasha",
    "How Time Folds and Space Dissolves",
    "The Guru Who Repositions Consciousness",
    # Conclusion
    "Living as Leela — The Divine Play Across All Lokas",
]

# Sanskrit shastras and key references from the satsang for the Researcher to locate
REFERENCE_SEEDS = [
    "Patanjali Yoga Sutras — Bandha Karana Shaithilyat Prachar Samvedanascha Chittasya Parasharira Aveshaha",
    "Yoga Vasistha — Utpatti Prakarana — Queen Leela's story narrated by Brahmarishi Vashishta to Rama",
    "Yoga Vasistha — Chitakasham Bhavadi Bhavedegam Dvitiyam Chitta Sambhavam Tritiyam Bhuta Sambhavam",
    "Yoga Vasistha — Yatha Swapne Nisha Dirgha Kshana Matra Pratiyate — time relativity verse",
    "Yoga Vasistha — Sankalpa Matre Vedam Jagat Sarvam Vasacharam — Sankalpa creates the universe",
    "Yoga Vasistha — Nirvikalpe Samadautu Chidhih Swatmanidhishtadi — Nirvikalpa Samadhi verse",
    "Kamikagama — Paramashiva describes himself as eternally 16",
    "Three Akashas: Chidakasha, Chittakasha, Bhutakasha",
    "Parakaya Pravesha — the ancient technology of consciousness entering another body",
    "Living Enlightenment by Sri Nithyananda — the source text for voice and storytelling style",
]


async def main():
    from workflow import run_pipeline

    cli = _parse_args()

    num_chapters = cli.get("chapters", len(CHAPTER_TITLES))
    num_chapters = max(3, min(20, num_chapters))
    words_per_chapter = cli.get("words", 2500)
    words_per_chapter = max(1000, min(8000, words_per_chapter))

    # Trim or pad chapter titles to match requested count
    titles = CHAPTER_TITLES[:num_chapters] if num_chapters <= len(CHAPTER_TITLES) else None

    pg_low, pg_high = _estimate_pages(num_chapters, words_per_chapter)
    total_words_est = num_chapters * words_per_chapter + 900

    print()
    print("=" * 72)
    print("  Book Generator v2 — June 24 Satsang Run")
    print("=" * 72)
    print()
    print("  Title      : The Multiverse Within — Secrets of Parakaya Pravesha")
    print("  Source     : June 24, 2026 Satsang — Tiruvannamalai / Kailasa Ginibisa")
    print(f"  Chapters   : {num_chapters}")
    print(f"  Words/ch   : {words_per_chapter:,}")
    print(f"  Est. words : ~{total_words_est:,}")
    print(f"  Est. pages : ~{pg_low}–{pg_high} pages (Word doc, Palatino 11pt)")
    print()

    book_input = {
        "title": "The Multiverse Within — Secrets of Parakaya Pravesha",
        "subtitle": "The Ancient Technology of Consciousness Travel Across Bodies, Lives, and Lokas",
        "author": "The SPH Bhagwan Sri Nithyananda Paramashivam",
        "num_chapters": num_chapters,
        "words_per_chapter": words_per_chapter,
        "pov": "first person",
        "tone": "spiritual-conversational",
        "reading_level": "intermediate",
        "language": "English",
        "synopsis": BOOK_SYNOPSIS.strip(),
        "themes": BOOK_THEMES,
        "target_audience": (
            "Spiritual seekers, Hindu devotees, meditators, and truth-seekers who want "
            "to go beyond the surface of existence and experience the living science of "
            "consciousness travel as taught in Sanatana Hindu Dharma."
        ),
        "chapter_titles": titles,
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

    print(f"\n  Final output : {state.docx_path}")
    total = sum(c.final_word_count for c in state.edited.values())
    foreword_wc = len(getattr(state, "_foreword", "").split())
    bene_wc = len(getattr(state, "_benediction", "").split())
    grand_total = total + foreword_wc + bene_wc
    actual_low = round(grand_total / 320)
    actual_high = round(grand_total / 280)
    print(f"  Total words  : {grand_total:,}  "
          f"(chapters: {total:,} | foreword: {foreword_wc} | benediction: {bene_wc})")
    print(f"  Est. pages   : ~{actual_low}–{actual_high} pages")
    if state.all_source_links:
        print(f"  YouTube links: {len(state.all_source_links)} source video(s) matched")
    if state.status["errors"]:
        print(f"  Errors       : {state.status['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
