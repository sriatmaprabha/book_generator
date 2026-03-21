"""
Minimal test run — generates a 2-chapter book to validate the full pipeline.

Usage:
    python test_run.py
"""

import asyncio
import sys

async def main():
    from workflow import run_pipeline

    test_input = {
        "title": "The Witness Within",
        "subtitle": "A Short Guide to Inner Observation",
        "author": "Test Author",
        "num_chapters": 3,
        "words_per_chapter": 1500,
        "pov": "first person",
        "tone": "spiritual-conversational",
        "reading_level": "intermediate",
        "language": "English",
        "synopsis": (
            "A concise exploration of the practice of witnessing — the ability to observe "
            "your own thoughts without attachment. Each chapter guides the reader through "
            "a story, a teaching, and a hands-on exercise."
        ),
        "themes": ["witnessing", "awareness", "inner stillness"],
        "target_audience": "Spiritual seekers new to meditation",
        "reference_sources": [],
        "section_template": ["opening_story", "teaching", "practical_exercise", "closing_bridge"],
    }

    print("\n  Running 2-chapter test pipeline...")
    print("  This validates: Intake -> Architect -> Research -> Write -> Edit -> Design\n")

    state = await run_pipeline(raw_input=test_input, skip_mcp=False)

    # Verify outputs
    errors = []
    if state.blueprint is None:
        errors.append("No blueprint generated")
    if len(state.drafts) != 3:
        errors.append(f"Expected 3 drafts, got {len(state.drafts)}")
    if len(state.edited) != 3:
        errors.append(f"Expected 3 edited chapters, got {len(state.edited)}")
    if state.docx_path and state.docx_path.exists():
        print(f"\n  DOCX exists: {state.docx_path} ({state.docx_path.stat().st_size} bytes)")
    else:
        errors.append("DOCX file not created")

    if errors:
        print("\n  ISSUES:")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)
    else:
        print("\n  ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
