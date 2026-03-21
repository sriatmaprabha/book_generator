"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         KAILASA  —  Agentic Book Generation Pipeline  v2                     ║
║         Fixed: context overflow + safer NVIDIA default model                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Key fixes in v2:
  • compress_tool_results=True  on every agent and the team
  • max_tool_calls_from_history=2  to prevent history bloat
  • Agents instructed to fetch ONLY targeted snippets from MCP
    (table of contents + 1 sample chapter, NOT full books)
  • Inter-agent handoff uses compact structured summaries, not raw MCP dumps
  • Writer writes one chapter at a time in separate focused prompts,
    then Administrator stitches them together
  • Model: meta/llama-3.3-70b-instruct (build.nvidia.com)

Usage:
    pip install agno openai mcp
    export NVIDIA_API_KEY="nvapi-..."
    python book_workflow.py
"""

import asyncio
import os
import sys
from pathlib import Path
from textwrap import dedent

from agno.agent import Agent
from agno.models.nvidia import Nvidia
from agno.team.team import Team
from agno.team.mode import TeamMode
from agno.tools.mcp import MCPTools


def configure_console_encoding() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

# ─────────────────────────────────────────────────────────────────────────────
# Model  — meta/llama-3.3-70b-instruct via build.nvidia.com
# Use NVIDIA_MODEL_ID to override this if your account exposes a different model.
# ─────────────────────────────────────────────────────────────────────────────
# Common model IDs on build.nvidia.com often available in Agno's NVIDIA gateway:
#   meta/llama-3.3-70b-instruct
#   meta/llama-3.1-70b-instruct
#   nvidia/llama-3.1-nemotron-70b-instruct
# Change the id below to match what appears in your NVIDIA playground.
NVIDIA_MODEL_ID = os.getenv("NVIDIA_MODEL_ID", "meta/llama-3.3-70b-instruct")

def model() -> Nvidia:
    """Fresh model instance (avoids shared state between agents)."""
    return Nvidia(
        id=NVIDIA_MODEL_ID,
        max_tokens=4096,         # cap each agent's output to stay safe
    )

# ─────────────────────────────────────────────────────────────────────────────
# MCP URLs
# ─────────────────────────────────────────────────────────────────────────────
JNANALAYA_URL = "https://jnanalaya.kailasa.ai/mcp"
SPH_BOOKS_URL = "https://jnanalaya.nithyananda.ai/mcp"

# ─────────────────────────────────────────────────────────────────────────────
# Topic prompt
# ─────────────────────────────────────────────────────────────────────────────
def ask_topic() -> str:
    print()
    print("=" * 70)
    print("  📚  KAILASA Agentic Book Generation Pipeline  (v2)")
    print("=" * 70)
    print()
    topic = input(
        "  🔷  What topic should the book be about?\n  ➜  "
    ).strip()
    if not topic:
        topic = "The inner science of Nithya Dhyaan meditation"
        print(f"\n  (Using default: {topic})")
    print()
    return topic


# ─────────────────────────────────────────────────────────────────────────────
# Shared MCP tool builder — compress_tool_results prevents context explosion
# ─────────────────────────────────────────────────────────────────────────────
async def connect_mcp(url: str, label: str) -> MCPTools:
    tools = MCPTools(
        transport="streamable-http",
        url=url,
        timeout_seconds=60,
    )
    await tools.connect()
    print(f"  ✅  {label} connected")
    return tools


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Designer
# Fetches: ONLY the ToC + 1 sample chapter from Living Enlightenment
# Outputs: compact Markdown blueprint (chapter titles + outlines)
# ─────────────────────────────────────────────────────────────────────────────
async def run_designer(topic: str, jnanalaya: MCPTools, sph: MCPTools) -> str:
    agent = Agent(
        name="Book Designer",
        role="Design book blueprint from Living Enlightenment structure",
        model=model(),
        tools=[jnanalaya, sph],
        description=dedent("""\
            You are a Book Designer. Your output must be SHORT and STRUCTURED.
            You have MCP access to Kailasa Jnanalaya and SPH Books.
        """),
        instructions=[
            # ── MCP fetch limits ──────────────────────────────────────────
            "EXACT TOOL NAMES:",
            "  • Kailasa Jnanalaya: list-books, resolve-book, get-chapters, read-chapter, search-books, search-sections",
            "  • SPH Books: list_books, get_book, get_book_by_slug, list_chapters, get_chapter, get_chapter_by_slug, search_chapters",
            "  • Do NOT invent tool names like search_books for Kailasa Jnanalaya.",
            "USE MCP TOOLS — but fetch MINIMALLY:",
            "  • From Jnanalaya: search for 'Living Enlightenment', then fetch "
            "    ONLY its table of contents (list of chapter titles). Do NOT "
            "    fetch full chapter content.",
            "  • From SPH Books: search for 2–3 relevant verses for the topic. "
            "    Fetch only title + first 2 sentences of each. No full chapters.",
            # ── Output format ─────────────────────────────────────────────
            "Produce a blueprint with EXACTLY this structure (keep it compact):",
            "",
            "BOOK TITLE: [title]",
            "TONE: [2 sentences describing tone and speech style]",
            "JOKE POLICY: [1 sentence — type of humor to use]",
            "",
            "CHAPTERS (7 total, each as a short bullet block):",
            "Chapter N: [Title]",
            "  - Core teaching: [1 sentence]",
            "  - Story seed: [1 sentence premise]",
            "  - Verse ref: [book name + chapter/verse number only — no full text]",
            "  - Joke seed: [1 sentence premise for the joke]",
            "",
            "Keep the ENTIRE blueprint under 800 words. No extra prose.",
        ],
        compress_tool_results=True,
        max_tool_calls_from_history=2,
        markdown=True,
    )

    print("\n  📐  Phase 1 — Book Designer running...")
    response = await agent.arun(
        f"Design a 7-chapter book blueprint for the topic: «{topic}». "
        "Fetch only the Living Enlightenment table of contents for structure reference."
    )
    result = str(response.content) if response.content else ""
    print("  ✅  Blueprint ready.")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Writer (one chapter at a time to avoid context overflow)
# Each chapter call is independent — small, focused context
# ─────────────────────────────────────────────────────────────────────────────
async def run_writer_chapter(
    chapter_num: int,
    chapter_brief: str,
    topic: str,
    jnanalaya: MCPTools,
    sph: MCPTools,
) -> str:
    agent = Agent(
        name="Book Writer",
        role="Write one book chapter with story, verse, exercise, and joke",
        model=model(),
        tools=[jnanalaya, sph],
        description=dedent("""\
            You are a spiritual author writing in the warm, story-rich style of
            SPH Nithyananda's 'Living Enlightenment'.
        """),
        instructions=[
            "EXACT TOOL NAMES:",
            "  • Kailasa Jnanalaya: list-books, resolve-book, get-chapters, read-chapter, search-books, search-sections",
            "  • SPH Books: list_books, get_book, get_book_by_slug, list_chapters, get_chapter, get_chapter_by_slug, search_chapters",
            "  • Do NOT invent tool names.",
            "USE MCP TOOLS — fetch ONLY what this chapter needs:",
            "  • From SPH Books: fetch the ONE verse reference listed in the "
            "    chapter brief. Get only the verse text (under 100 words).",
            "  • From Jnanalaya: optionally fetch 1 short paragraph from "
            "    Living Enlightenment as a prose style reference. Nothing more.",
            "",
            "Write this chapter with exactly these sections:",
            "## Chapter N: [Title]",
            "### Opening Story  (~300 words)",
            "  A vivid teaching story illustrating the core teaching.",
            "### The Teaching  (~400 words)",
            "  The core insight, weaving in the verse quote naturally.",
            "  Include the verse as a blockquote: > [verse text]  — [source]",
            "### Practical Exercise  (~150 words)",
            "  A concrete contemplation or sadhana for the reader.",
            "### [Natural joke or witty observation woven into teaching]",
            "  1–2 sentences of warm, spiritual humor. Label with 😄",
            "### Closing Bridge  (~100 words)",
            "  A paragraph flowing into the next chapter's theme.",
            "",
            "Total chapter length: 900–1100 words. Keep it tight.",
            "Do NOT add extra sections or padding.",
        ],
        compress_tool_results=True,
        max_tool_calls_from_history=2,
        markdown=True,
    )

    response = await agent.arun(
        f"Write Chapter {chapter_num} of the book on «{topic}».\n\n"
        f"CHAPTER BRIEF:\n{chapter_brief}"
    )
    return str(response.content) if response.content else f"[Chapter {chapter_num} failed]"


async def run_writer(
    blueprint: str,
    topic: str,
    jnanalaya: MCPTools,
    sph: MCPTools,
) -> str:
    """Parse blueprint into chapter briefs, write each chapter independently."""
    print("\n  ✍️   Phase 2 — Book Writer running (chapter by chapter)...")

    # Split blueprint into per-chapter briefs
    chapters_raw = []
    current = []
    for line in blueprint.split("\n"):
        if line.strip().startswith("Chapter ") and current:
            chapters_raw.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chapters_raw.append("\n".join(current))

    # Keep only actual chapter blocks (filter out preamble)
    chapter_briefs = [c for c in chapters_raw if c.strip().startswith("Chapter ")]

    if not chapter_briefs:
        # Fallback: treat entire blueprint as one set, write 7 chapters
        print("  ⚠️  Could not parse chapter briefs — writing 7 generic chapters")
        chapter_briefs = [
            f"Chapter {i}: Based on the topic «{topic}». Follow the blueprint."
            for i in range(1, 8)
        ]

    all_chapters = []
    for i, brief in enumerate(chapter_briefs, 1):
        print(f"     Writing Chapter {i}/{len(chapter_briefs)}...")
        chapter_text = await run_writer_chapter(i, brief, topic, jnanalaya, sph)
        all_chapters.append(chapter_text)
        # Small pause to avoid rate-limiting
        await asyncio.sleep(1)

    draft = "\n\n---\n\n".join(all_chapters)
    print("  ✅  Full draft ready.")
    return draft


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Proofreader (chapter by chapter to avoid overflow)
# ─────────────────────────────────────────────────────────────────────────────
async def run_proofreader_chapter(
    chapter_text: str,
    chapter_num: int,
    jnanalaya: MCPTools,
    sph: MCPTools,
) -> str:
    agent = Agent(
        name="Book Proofreader",
        role="Proofread and polish one chapter",
        model=model(),
        tools=[sph],          # only needs SPH to verify verse accuracy
        description="You are a senior editor deeply familiar with SPH's writing style.",
        instructions=[
            "Proofread this ONE chapter. Fix grammar, flow, and consistency.",
            "EXACT SPH tool names: list_books, get_book, get_book_by_slug, list_chapters, get_chapter, get_chapter_by_slug, search_chapters.",
            "Do NOT invent tool names.",
            "If the verse quote looks wrong, use SPH Books MCP to verify it.",
            "Ensure the joke is present and feels natural — tighten if needed.",
            "Ensure the story opening is vivid and gripping.",
            "Return the COMPLETE polished chapter text only.",
            "Do not add commentary — just return the improved chapter.",
            "Keep edits minimal — preserve the author's voice.",
        ],
        compress_tool_results=True,
        max_tool_calls_from_history=1,
        markdown=True,
    )

    response = await agent.arun(
        f"Proofread Chapter {chapter_num}:\n\n{chapter_text}"
    )
    return str(response.content) if response.content else chapter_text


async def run_proofreader(
    draft: str,
    jnanalaya: MCPTools,
    sph: MCPTools,
) -> str:
    print("\n  🔍  Phase 3 — Proofreader running (chapter by chapter)...")
    chapters = draft.split("\n\n---\n\n")
    polished = []
    for i, ch in enumerate(chapters, 1):
        print(f"     Proofreading Chapter {i}/{len(chapters)}...")
        polished_ch = await run_proofreader_chapter(ch, i, jnanalaya, sph)
        polished.append(polished_ch)
        await asyncio.sleep(1)
    print("  ✅  Proofreading complete.")
    return "\n\n---\n\n".join(polished)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Administrator compiles the final book
# ─────────────────────────────────────────────────────────────────────────────
def compile_book(topic: str, blueprint: str, polished_draft: str) -> str:
    """Administrator assembles final Markdown book."""
    # Extract title from blueprint
    title = topic
    for line in blueprint.split("\n"):
        if line.startswith("BOOK TITLE:"):
            title = line.replace("BOOK TITLE:", "").strip()
            break

    # Build table of contents from chapter headings
    toc_lines = ["## 📖 Table of Contents\n"]
    for line in polished_draft.split("\n"):
        if line.startswith("## Chapter"):
            ch_title = line.replace("## ", "").strip()
            anchor = ch_title.lower().replace(" ", "-").replace(":", "").replace(",", "")
            toc_lines.append(f"- [{ch_title}](#{anchor})")

    toc = "\n".join(toc_lines)

    final = f"""# {title}

> *Inspired by the teachings of SPH Bhagavan Sri Nithyananda Paramashivam*
> *Generated by KAILASA Agentic Book Generation Pipeline*

---

{toc}

---

## Foreword

This book is an offering — a distillation of living wisdom transmitted through
millennia, now spoken fresh for the modern seeker. What you hold is not merely
a collection of ideas but a set of keys. Each chapter is a door. Each story is
a mirror. Each joke is a reminder not to take the ego too seriously.

Read slowly. Try the exercises. Let the verses land. And above all, remember:
the destination is not somewhere else. It is exactly where you are standing,
if only you would look.

*— KAILASA Ministry of Digital Services*

---

{polished_draft}

---

## Sources

This book was generated using the following KAILASA knowledge sources:

- **Kailasa Jnanalaya** — [jnanalaya.kailasa.ai](https://jnanalaya.kailasa.ai)
  *Living Enlightenment* — structural and stylistic reference
- **SPH Books** — [jnanalaya.nithyananda.ai](https://jnanalaya.nithyananda.ai)
  Verse and sutra references from SPH Bhagavan Sri Nithyananda Paramashivam

---

## Benediction

May the words in these pages become a living experience within you.
May every story remind you of your own story.
May every teaching become your own knowing.
May the Divine within you awaken, now and always.

*Nithyanandam.*
"""
    return final


# ─────────────────────────────────────────────────────────────────────────────
# Save output
# ─────────────────────────────────────────────────────────────────────────────
def save_book(content: str, topic: str, output_dir: str = "output") -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic)[:50]
    path = out / f"{slug.strip().replace(' ', '_')}_book.md"
    path.write_text(content, encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────
async def run_pipeline(topic: str) -> None:
    print("  🔌  Connecting to MCP servers...")

    jnanalaya = await connect_mcp(JNANALAYA_URL, "Kailasa Jnanalaya MCP")
    sph       = await connect_mcp(SPH_BOOKS_URL,  "SPH Books MCP       ")

    try:
        # Phase 1 — Design
        blueprint = await run_designer(topic, jnanalaya, sph)
        print("\n  📋  Blueprint preview (first 400 chars):")
        print("  " + blueprint[:400].replace("\n", "\n  "))
        print()

        # Phase 2 — Write (chapter by chapter)
        draft = await run_writer(blueprint, topic, jnanalaya, sph)

        # Phase 3 — Proofread (chapter by chapter)
        polished = await run_proofreader(draft, jnanalaya, sph)

        # Phase 4 — Compile (administrator, no LLM needed — pure assembly)
        print("\n  📦  Phase 4 — Administrator compiling final book...")
        final_book = compile_book(topic, blueprint, polished)

        # Save
        out_path = save_book(final_book, topic)
        word_count = len(final_book.split())

        print()
        print("=" * 70)
        print(f"  ✅  Book generation complete!")
        print(f"  📄  Saved: {out_path.resolve()}")
        print(f"  📊  ~{word_count:,} words")
        print("=" * 70)
        print()

    finally:
        await jnanalaya.close()
        await sph.close()
        print("  🔌  MCP connections closed.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    configure_console_encoding()
    topic = ask_topic()
    asyncio.run(run_pipeline(topic))
