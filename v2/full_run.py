"""
Full book generation — asks for topic, then generates a 7-chapter book
in the voice of The SPH Bhagwan Sri Nithyananda Paramashivam.
"""

import asyncio


async def main():
    from workflow import run_pipeline

    print()
    print("=" * 72)
    print("  Book Generator v2 — Full Run")
    print("=" * 72)
    print()
    topic = input("  What topic should the book be written on?\n  > ").strip()
    if not topic:
        topic = "The inner science of witnessing consciousness"
        print(f"  Using default: {topic}")
    print()

    book_input = {
        "title": topic,
        "subtitle": f"Discovering the Science of {topic} Through Living Enlightenment",
        "author": "The SPH Bhagwan Sri Nithyananda Paramashivam",
        "num_chapters": 7,
        "words_per_chapter": 2500,
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
    print(f"  Total words: {total}")
    print(f"  Errors: {state.status['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
