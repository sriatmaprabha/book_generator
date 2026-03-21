"""
Full 7-chapter book: "Does Shiva Reside Inside Me?"
"""

import asyncio


async def main():
    from workflow import run_pipeline

    book_input = {
        "title": "Does Shiva Reside Inside Me?",
        "subtitle": "Discovering Paramashiva Within Through the Science of Living Enlightenment",
        "author": "The SPH Bhagwan Sri Nithyananda Paramashivam",
        "num_chapters": 7,
        "words_per_chapter": 2500,
        "pov": "first person",
        "tone": "spiritual-conversational",
        "reading_level": "intermediate",
        "language": "English",
        "synopsis": (
            "This book is a direct transmission from The SPH Nithyananda Paramashivam "
            "exploring the most intimate question a seeker can ask: Does Shiva — Paramashiva, "
            "the ultimate cosmic consciousness — truly reside within me? Through immersive "
            "first-person stories from ashram life, profound shastric revelations from the "
            "Vedas, Agamas, and Upanishads, and practical spiritual techniques, each chapter "
            "peels back a layer of illusion to reveal that Paramashiva is not a distant deity "
            "but the very fabric of your inner space. The book moves from the initial doubt "
            "('Am I worthy?') through the discovery of the Atman-Shiva identity, the role of "
            "the Guru as the living mirror, the power of initiation (diksha), the science of "
            "the five koshas as veils over Shiva, the practice of Shiva consciousness in "
            "daily life, and culminates in the direct experience of Shivoham — 'I am Shiva'. "
            "Every teaching is anchored in exact Sanskrit verses with faithful translations."
        ),
        "themes": [
            "Paramashiva as inner reality",
            "Shivoham — I am Shiva",
            "Atman-Brahman identity",
            "Guru as mirror of Shiva",
            "diksha and initiation",
            "pancha kosha — five sheaths",
            "living enlightenment",
            "Agamic science of consciousness",
        ],
        "target_audience": "Spiritual seekers, Hindu devotees, and meditators exploring Shaiva philosophy",
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
