"""
Agno-native multi-agent book generation workflow.

This entrypoint keeps the existing book_workflow.py intact and adds a
Workflow-driven orchestration layer with explicit administrator checkpoints.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from agno.agent import Agent
from agno.models.nvidia import Nvidia
from agno.run.agent import RunStatus
from agno.run.workflow import WorkflowRunOutput
from agno.tools.mcp import MCPTools
from agno.workflow import OnError, Step, StepInput, StepOutput, Workflow


JNANALAYA_URL = "https://jnanalaya.kailasa.ai/mcp"
SPH_BOOKS_URL = "https://jnanalaya.nithyananda.ai/mcp"

NVIDIA_MODEL_ID = os.getenv("NVIDIA_MODEL_ID", "meta/llama-3.3-70b-instruct")
MODEL_CANDIDATES = [
    NVIDIA_MODEL_ID,
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
]
ACTIVE_NVIDIA_MODEL_ID = NVIDIA_MODEL_ID
MAX_AGENT_OUTPUT_TOKENS = int(os.getenv("BOOK_AGENT_MAX_TOKENS", "8192"))
MIN_CHAPTERS = 7
MAX_CHAPTERS = 10
MAX_STAGE_RETRIES = 2
# Chapter depth targets
MIN_CHAPTER_WORDS = 2000
MAX_CHAPTER_WORDS = 3500
MIN_SECTION_PARAGRAPHS = 3  # minimum paragraphs per section (Opening Story, Teaching, etc.)
DEFAULT_OUTPUT_ROOT = Path(os.getenv("BOOK_WORKFLOW_OUTPUT_DIR", "output"))

RUNTIME_RESOURCES: Dict[str, Dict[str, Any]] = {}


class ChapterBrief(BaseModel):
    number: int = Field(..., ge=1)
    title: str
    core_teaching: str
    story_seed: str           # 3+ sentence narrative seed (setting, protagonist, conflict, turning point)
    narrative_arc: str        # multi-sentence teaching progression arc for this chapter
    verse_reference: str
    joke_seed: str            # warm anecdote / self-deprecating story seed (NOT a punchline)
    bridge_to_next: str       # narrative hook leading into the next chapter
    target_word_count: int = Field(default=2500, ge=MIN_CHAPTER_WORDS, le=MAX_CHAPTER_WORDS)


class BookBlueprint(BaseModel):
    book_title: str
    tone: str
    speech_level: str
    speech_style: str
    joke_policy: str
    structure_notes: str
    chapter_count: int = Field(..., ge=MIN_CHAPTERS, le=MAX_CHAPTERS)
    chapters: List[ChapterBrief] = Field(..., min_length=MIN_CHAPTERS, max_length=MAX_CHAPTERS)


class AdminReview(BaseModel):
    approved: bool
    issues: List[str] = Field(default_factory=list)
    retry_target: Literal["designer", "writer", "proofreader", "none"] = "none"
    revision_notes: str = ""


class ChapterDraft(BaseModel):
    chapter_number: int = Field(..., ge=1)
    title: str
    markdown: str
    word_count: int = Field(..., ge=1)
    summary: str


class CompiledBookMetadata(BaseModel):
    topic: str
    title: str
    foreword: str
    benediction: str
    source_notes: List[str]
    chapter_count: int = Field(..., ge=MIN_CHAPTERS, le=MAX_CHAPTERS)
    estimated_word_count: int = Field(..., ge=1)


def build_model() -> Nvidia:
    return Nvidia(id=ACTIVE_NVIDIA_MODEL_ID, max_tokens=MAX_AGENT_OUTPUT_TOKENS)


def ask_topic() -> str:
    print()
    print("=" * 72)
    print("  Agno Multi-Agent Book Generator")
    print("=" * 72)
    print()
    topic = input("  What topic should the book be created on?\n  > ").strip()
    if not topic:
        topic = "The inner science of conscious living"
        print(f"\n  Using default topic: {topic}")
    print()
    return topic


def slugify(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in (" ", "-", "_") else "_" for ch in value)
    compact = "_".join(cleaned.split())
    return compact[:80] or "book"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def render_blueprint_markdown(blueprint: BookBlueprint) -> str:
    lines = [
        f"# {blueprint.book_title}",
        "",
        f"- Tone: {blueprint.tone}",
        f"- Speech level: {blueprint.speech_level}",
        f"- Speech style: {blueprint.speech_style}",
        f"- Joke policy: {blueprint.joke_policy}",
        "",
        "## Structure Notes",
        blueprint.structure_notes,
        "",
        "## Chapter Briefs",
        "",
    ]
    for chapter in blueprint.chapters:
        lines.extend(
            [
                f"### Chapter {chapter.number}: {chapter.title}",
                f"- Core teaching: {chapter.core_teaching}",
                f"- Story seed: {chapter.story_seed}",
                f"- Narrative arc: {chapter.narrative_arc}",
                f"- Verse reference: {chapter.verse_reference}",
                f"- Joke seed: {chapter.joke_seed}",
                f"- Bridge to next: {chapter.bridge_to_next}",
                f"- Target word count: {chapter.target_word_count}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def build_table_of_contents(chapters: List[ChapterDraft]) -> str:
    toc_lines = ["## Table of Contents", ""]
    for chapter in chapters:
        heading = f"Chapter {chapter.chapter_number}: {chapter.title}"
        anchor = heading.lower().replace(" ", "-").replace(":", "").replace(",", "")
        toc_lines.append(f"- [{heading}](#{anchor})")
    return "\n".join(toc_lines)


def assemble_book(markdown_metadata: CompiledBookMetadata, chapters: List[ChapterDraft]) -> str:
    chapter_blocks = "\n\n---\n\n".join(chapter.markdown.strip() for chapter in chapters)
    toc = build_table_of_contents(chapters)
    sources = "\n".join(f"- {note}" for note in markdown_metadata.source_notes)

    return dedent(
        f"""\
        # {markdown_metadata.title}

        > Generated for the topic: {markdown_metadata.topic}

        ---

        {toc}

        ---

        ## Foreword

        {markdown_metadata.foreword}

        ---

        {chapter_blocks}

        ---

        ## Sources

        {sources}

        ---

        ## Benediction

        {markdown_metadata.benediction}
        """
    ).strip() + "\n"


def chapter_from_markdown(markdown: str, fallback_number: int, fallback_title: str, summary: str) -> ChapterDraft:
    match = re.search(r"^##\s+Chapter\s+(\d+):\s+(.+)$", markdown, re.MULTILINE)
    chapter_number = fallback_number
    title = fallback_title
    if match:
        chapter_number = int(match.group(1))
        title = match.group(2).strip()
    return ChapterDraft(
        chapter_number=chapter_number,
        title=title,
        markdown=markdown,
        word_count=len(markdown.split()),
        summary=summary,
    )


def get_session_state(step_input: StepInput) -> Dict[str, Any]:
    workflow_session = step_input.workflow_session
    if workflow_session is None:
        raise RuntimeError("Workflow session was not provided to the step executor.")
    if workflow_session.session_data is None:
        workflow_session.session_data = {}
    state = workflow_session.session_data.setdefault("state", {})
    if not isinstance(state, dict):
        raise RuntimeError("Workflow session state is not a dictionary.")
    return state


def get_runtime(step_input: StepInput) -> Dict[str, Any]:
    workflow_session = step_input.workflow_session
    if workflow_session is None:
        raise RuntimeError("Workflow session missing while fetching runtime resources.")
    runtime = RUNTIME_RESOURCES.setdefault(workflow_session.session_id, {})
    return runtime


def compute_word_count(chapters: List[ChapterDraft], metadata: Optional[CompiledBookMetadata] = None) -> int:
    total = sum(len(chapter.markdown.split()) for chapter in chapters)
    if metadata is not None:
        total += len(metadata.foreword.split()) + len(metadata.benediction.split())
    return total


def blueprint_issues(blueprint: BookBlueprint) -> List[str]:
    issues: List[str] = []
    if not (MIN_CHAPTERS <= blueprint.chapter_count <= MAX_CHAPTERS):
        issues.append(f"Blueprint chapter_count must be between {MIN_CHAPTERS} and {MAX_CHAPTERS}.")
    if len(blueprint.chapters) != blueprint.chapter_count:
        issues.append("Blueprint chapter_count does not match the number of chapter briefs.")
    if not blueprint.tone.strip():
        issues.append("Blueprint is missing tone guidance.")
    if not blueprint.speech_level.strip():
        issues.append("Blueprint is missing speech level guidance.")
    if not blueprint.speech_style.strip():
        issues.append("Blueprint is missing speech style guidance.")
    if not blueprint.joke_policy.strip():
        issues.append("Blueprint is missing joke policy guidance.")
    numbers = [chapter.number for chapter in blueprint.chapters]
    if numbers != list(range(1, len(blueprint.chapters) + 1)):
        issues.append("Chapter numbers must be sequential starting from 1.")
    for chapter in blueprint.chapters:
        if not chapter.verse_reference.strip():
            issues.append(f"Chapter {chapter.number} is missing a verse reference.")
    return issues


def chapter_issues(chapter: ChapterDraft, expected_number: int, expected_title: str) -> List[str]:
    issues: List[str] = []
    if chapter.chapter_number != expected_number:
        issues.append(f"Expected chapter number {expected_number}, got {chapter.chapter_number}.")
    if chapter.title.strip() != expected_title.strip():
        issues.append(f"Expected chapter title '{expected_title}', got '{chapter.title}'.")
    required_markers = [
        "## Chapter",
        "### Opening Story",
        "### The Teaching",
        "### Practical Exercise",
        "### Humor",
        "### Closing Bridge",
    ]
    for marker in required_markers:
        if marker not in chapter.markdown:
            issues.append(f"Chapter {expected_number} is missing the section '{marker}'.")
    if chapter.word_count < MIN_CHAPTER_WORDS:
        issues.append(
            f"Chapter {expected_number} is too short ({chapter.word_count} words). "
            f"Minimum required: {MIN_CHAPTER_WORDS} words. Each section needs {MIN_SECTION_PARAGRAPHS}+ paragraphs."
        )
    return issues


def chapter_list_issues(chapters: List[ChapterDraft], blueprint: BookBlueprint) -> List[str]:
    issues: List[str] = []
    if len(chapters) != blueprint.chapter_count:
        issues.append("Draft chapter count does not match the approved blueprint.")
        return issues
    for expected, actual in zip(blueprint.chapters, chapters):
        issues.extend(chapter_issues(actual, expected.number, expected.title))
    return issues


async def connect_mcp(url: str, label: str) -> MCPTools:
    try:
        tools = MCPTools(transport="streamable-http", url=url, timeout_seconds=60)
        await tools.connect()
        print(f"  Connected: {label}")
        return tools
    except Exception as exc:
        raise RuntimeError(
            f"Failed to connect to {label} at {url}. "
            "Check network access, MCP availability, and transport compatibility."
        ) from exc


def tool_result_content(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    return str(result)


def build_reference_tools(jnanalaya: MCPTools, sph: MCPTools) -> List[Any]:
    async def jn_search_books(query: str, limit: int = 10) -> str:
        """Search Kailasa Jnanalaya books. Use this to find Living Enlightenment."""
        return tool_result_content(await jnanalaya.functions["search-books"].entrypoint(query=query, limit=limit))

    async def jn_resolve_book(query: str, limit: int = 5) -> str:
        """Resolve a Kailasa Jnanalaya book title or topic to an exact book record."""
        return tool_result_content(await jnanalaya.functions["resolve-book"].entrypoint(query=query, limit=limit))

    async def jn_get_chapters(bookSlug: str) -> str:
        """Get chapter metadata for a Kailasa Jnanalaya book using its bookSlug."""
        return tool_result_content(await jnanalaya.functions["get-chapters"].entrypoint(bookSlug=bookSlug))

    async def jn_read_chapter(bookSlug: str, chapterSlug: str) -> str:
        """Read a Kailasa Jnanalaya chapter by bookSlug and chapterSlug."""
        return tool_result_content(
            await jnanalaya.functions["read-chapter"].entrypoint(bookSlug=bookSlug, chapterSlug=chapterSlug)
        )

    async def jn_search_sections(query: str, limit: int = 10) -> str:
        """Search Kailasa Jnanalaya sections for a precise teaching or phrase."""
        return tool_result_content(await jnanalaya.functions["search-sections"].entrypoint(query=query, limit=limit))

    async def sph_search_chapters(query: str, book_id: Optional[str] = None, page: int = 1, limit: int = 25) -> str:
        """Search SPH book chapters for verses and relevant passages."""
        return tool_result_content(
            await sph.functions["search_chapters"].entrypoint(query=query, book_id=book_id, page=page, limit=limit)
        )

    async def sph_get_chapter(chapter_id: str) -> str:
        """Fetch a full SPH chapter by chapter_id."""
        return tool_result_content(await sph.functions["get_chapter"].entrypoint(chapter_id=chapter_id))

    async def sph_get_chapter_by_slug(book_slug: str, chapter_slug: str) -> str:
        """Fetch a SPH chapter by book slug and chapter slug."""
        return tool_result_content(
            await sph.functions["get_chapter_by_slug"].entrypoint(book_slug=book_slug, chapter_slug=chapter_slug)
        )

    async def sph_list_chapters(book_id: str, page: int = 1, limit: int = 50) -> str:
        """List SPH chapters for a given book_id."""
        return tool_result_content(await sph.functions["list_chapters"].entrypoint(book_id=book_id, page=page, limit=limit))

    async def sph_get_book(book_id: str) -> str:
        """Fetch a SPH book by book_id."""
        return tool_result_content(await sph.functions["get_book"].entrypoint(book_id=book_id))

    async def sph_get_book_by_slug(slug: str) -> str:
        """Fetch a SPH book by slug."""
        return tool_result_content(await sph.functions["get_book_by_slug"].entrypoint(slug=slug))

    return [
        jn_search_books,
        jn_resolve_book,
        jn_get_chapters,
        jn_read_chapter,
        jn_search_sections,
        sph_search_chapters,
        sph_get_chapter,
        sph_get_chapter_by_slug,
        sph_list_chapters,
        sph_get_book,
        sph_get_book_by_slug,
    ]


def build_sph_tools(sph: MCPTools) -> List[Any]:
    async def sph_search_chapters(query: str, book_id: Optional[str] = None, page: int = 1, limit: int = 25) -> str:
        """Search SPH book chapters for verses and relevant passages."""
        return tool_result_content(
            await sph.functions["search_chapters"].entrypoint(query=query, book_id=book_id, page=page, limit=limit)
        )

    async def sph_get_chapter(chapter_id: str) -> str:
        """Fetch a full SPH chapter by chapter_id."""
        return tool_result_content(await sph.functions["get_chapter"].entrypoint(chapter_id=chapter_id))

    async def sph_get_chapter_by_slug(book_slug: str, chapter_slug: str) -> str:
        """Fetch a SPH chapter by book slug and chapter slug."""
        return tool_result_content(
            await sph.functions["get_chapter_by_slug"].entrypoint(book_slug=book_slug, chapter_slug=chapter_slug)
        )

    async def sph_list_chapters(book_id: str, page: int = 1, limit: int = 50) -> str:
        """List SPH chapters for a given book_id."""
        return tool_result_content(await sph.functions["list_chapters"].entrypoint(book_id=book_id, page=page, limit=limit))

    async def sph_get_book(book_id: str) -> str:
        """Fetch a SPH book by book_id."""
        return tool_result_content(await sph.functions["get_book"].entrypoint(book_id=book_id))

    async def sph_get_book_by_slug(slug: str) -> str:
        """Fetch a SPH book by slug."""
        return tool_result_content(await sph.functions["get_book_by_slug"].entrypoint(slug=slug))

    return [
        sph_search_chapters,
        sph_get_chapter,
        sph_get_chapter_by_slug,
        sph_list_chapters,
        sph_get_book,
        sph_get_book_by_slug,
    ]


def parse_json_text(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"raw": raw}


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def choose_living_enlightenment_book(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target = "living enlightenment"
    for item in candidates:
        title = normalize_text(str(item.get("title", "")))
        if title == target:
            return item
    for item in candidates:
        title = normalize_text(str(item.get("title", "")))
        if target in title:
            return item
    return None


async def fetch_living_enlightenment_context(jnanalaya: MCPTools) -> str:
    candidates: List[Dict[str, Any]] = []
    for query in ["living enlightenment", "Living Enlightenment", "\"living enlightenment\""]:
        resolved = parse_json_text(
            tool_result_content(await jnanalaya.functions["resolve-book"].entrypoint(query=query, limit=5))
        )
        candidates.extend(resolved.get("matches", []) or [])
        searched = parse_json_text(
            tool_result_content(await jnanalaya.functions["search-books"].entrypoint(query=query, limit=10))
        )
        candidates.extend(searched.get("results", []) or [])
        chosen = choose_living_enlightenment_book(candidates)
        if chosen:
            book_slug = chosen.get("bookSlug")
            chapters_raw = parse_json_text(
                tool_result_content(await jnanalaya.functions["get-chapters"].entrypoint(bookSlug=book_slug))
            )
            chapters = chapters_raw.get("chapters", []) or chapters_raw.get("results", []) or []
            chapter_lines = []
            sample_snippet = ""
            for chapter in chapters[:10]:
                title = chapter.get("title") or chapter.get("chapterTitle") or chapter.get("chapterSlug")
                slug = chapter.get("chapterSlug") or chapter.get("slug")
                chapter_lines.append(f"- {title} ({slug})")
            if chapters:
                first = chapters[0]
                sample_raw = tool_result_content(
                    await jnanalaya.functions["read-chapter"].entrypoint(
                        bookSlug=book_slug, chapterSlug=first.get("chapterSlug") or first.get("slug")
                    )
                )
                sample_snippet = sample_raw[:1200]
            return dedent(
                f"""\
                Reference book: {chosen.get('title')}
                Book slug: {book_slug}
                Chapter list:
                {chr(10).join(chapter_lines) if chapter_lines else '- No chapter metadata returned'}

                Sample chapter excerpt:
                {sample_snippet or 'No sample chapter excerpt returned.'}
                """
            )

    return dedent(
        """\
        Reference book lookup fallback:
        The exact Living Enlightenment book record was not resolved from MCP during prefetch.
        Use a Living-Enlightenment-like structure: immersive opening story, core teaching,
        spiritual practice, humor, and a bridge into the next chapter.
        """
    )


async def fetch_relevant_verse_context(topic: str, sph: MCPTools, limit: int = 5) -> str:
    tools = {tool.__name__: tool for tool in build_sph_tools(sph)}
    raw = await tools["sph_search_chapters"](topic, None, 1, limit)
    data = parse_json_text(raw)
    results = data.get("results") or data.get("items") or data.get("docs") or data.get("chapters") or []
    lines: List[str] = []
    for item in results[:limit]:
        title = item.get("title") or item.get("chapter_title") or item.get("slug") or "Untitled"
        snippet = item.get("excerpt") or item.get("summary") or item.get("content") or ""
        book = item.get("book_title") or item.get("book") or item.get("book_slug") or ""
        lines.append(f"- {book} | {title}: {str(snippet)[:240]}")
    return "\n".join(lines) if lines else "No verse search results returned."


async def fetch_style_and_verse_for_chapter(chapter_brief: ChapterBrief, sph: MCPTools) -> str:
    query = f"{chapter_brief.verse_reference} {chapter_brief.core_teaching}"
    return await fetch_relevant_verse_context(query, sph, limit=3)


def designer_agent(jnanalaya: MCPTools, sph: MCPTools) -> Agent:
    return Agent(
        name="Book Designer",
        role="Design a richly detailed book blueprint modeled semantically on Living Enlightenment.",
        model=build_model(),
        instructions=[
            "You are working from pre-fetched MCP context supplied in the prompt.",
            "Do not call extra tools or fetch additional data beyond what is given.",
            "Study the Living Enlightenment structure carefully: each chapter is a self-contained journey with"
            " an immersive opening story, progressively deepening teaching, a concrete practice, warm humor,"
            " and a narrative bridge into the next chapter.",
            "From SPH Books, select one specific verse per chapter that is directly relevant to its core teaching.",
            f"Produce exactly {MIN_CHAPTERS}-{MAX_CHAPTERS} chapters.",
            "Mirror Living Enlightenment semantically — vivid, story-rich, practically grounded, spiritually warm."
            " Do NOT copy source text verbatim.",
            "For EACH chapter brief you MUST provide:",
            "  - story_seed: AT LEAST 3 sentences describing the protagonist, setting, conflict, and turning point"
            "    of the opening story (not a one-liner summary).",
            "  - narrative_arc: 3-5 sentences tracing the teaching progression across the chapter"
            "    — how the insight unfolds, deepens, and lands.",
            "  - joke_seed: A 2-3 sentence warm anecdote or self-deprecating scenario that can be told as a story"
            "    (NOT a punchline; think 'the guru who always forgot his keys' style).",
            "  - bridge_to_next: 2-3 sentences forming a narrative hook that closes this chapter and"
            "    opens a question or tension that will be resolved in the next chapter.",
            "  - target_word_count: Set to 2500 for most chapters; use 3000 for pivotal teaching chapters.",
            "Set tone, speech level, speech style, and joke policy so the writer can maintain consistent voice.",
        ],
        markdown=False,
        compress_tool_results=True,
        max_tool_calls_from_history=2,
    )


def writer_agent(jnanalaya: MCPTools, sph: MCPTools) -> Agent:
    return Agent(
        name="Book Writer",
        role="Write a full, richly detailed chapter from an approved brief.",
        model=build_model(),
        instructions=[
            "You are working from pre-fetched MCP context supplied in the prompt.",
            "Use Living Enlightenment as a STYLE REFERENCE ONLY — original prose is required.",
            f"Every chapter MUST be between {MIN_CHAPTER_WORDS} and {MAX_CHAPTER_WORDS} words total.",
            f"Every section MUST contain at least {MIN_SECTION_PARAGRAPHS} substantial paragraphs (80+ words each).",
            "Section-by-section depth requirements:",
            "  ### Opening Story (target 400-500 words):",
            "    Write a complete short story with: vivid setting, a named protagonist, an inciting incident,"
            "    an internal struggle, a turning point, and a resolution that makes the teaching visceral."
            "    Do not summarise — narrate fully with sensory detail.",
            "  ### The Teaching (target 600-800 words):",
            "    Begin with the verse reference (quote it and unpack what it literally means)."
            "    Then layer 3-4 teaching insights that build on each other."
            "    Use real-world analogies (modern work, relationships, daily situations)."
            "    End this section with a clear, memorable 'enlightenment statement'.",
            "  ### Practical Exercise (target 350-500 words):",
            "    Name the practice clearly. Give: intention (1 paragraph), step-by-step instructions"
            "    (at least 5 numbered steps with 2+ sentences each), 'what you may notice' paragraph,"
            "    and 'common pitfalls' paragraph.",
            "  ### Humor (target 250-350 words):",
            "    Tell a warm, 3-4 paragraph anecdote — NOT a one-liner joke."
            "    The humor should be self-deprecating, spiritually aware, and arrive at a gentle insight."
            "    Think: 'the kind of story a master tells that makes you laugh and then sit quietly'.",
            "  ### Closing Bridge (target 200-300 words):",
            "    Reflect on what shifted in this chapter (1 paragraph). Pose an open question that"
            "    creates gentle tension. End with 1-2 sentences that gesture toward the next chapter's theme.",
            "Preserve the approved chapter title, tone, speech level, and speech style exactly.",
            "Write the chapter heading as: ## Chapter {N}: {Title}",
        ],
        markdown=False,
        compress_tool_results=True,
        max_tool_calls_from_history=2,
    )


def proofreader_agent(sph: MCPTools) -> Agent:
    return Agent(
        name="Book Proofreader",
        role="Proofread and deepen one chapter against the approved brief and verse reference.",
        model=build_model(),
        instructions=[
            "You are the final depth-and-polish pass for a spiritually rich book chapter.",
            "You are working from pre-fetched context supplied in the prompt.",
            "FIRST check depth before polishing:",
            f"  - If any section has fewer than {MIN_SECTION_PARAGRAPHS} paragraphs, EXPAND it with richer narrative,"
            f"    deeper insight, or additional examples until it meets the {MIN_SECTION_PARAGRAPHS}-paragraph minimum.",
            f"  - If the chapter total word count is below {MIN_CHAPTER_WORDS}, expand the thinnest sections first.",
            "THEN polish:",
            "  - Tighten grammar and fix awkward phrasing.",
            "  - Ensure the verse reference in 'The Teaching' is properly quoted and explained.",
            "  - Ensure 'Humor' is a warm anecdote (3-4 paragraphs), NOT a one-liner joke."
            "    If it is a punchline, rewrite it as a storytelling anecdote.",
            "  - Verify 'Closing Bridge' ends with a narrative hook toward the next chapter.",
            "Keep all five sections intact: Opening Story, The Teaching, Practical Exercise, Humor, Closing Bridge.",
            "Return the COMPLETE revised chapter markdown only — no commentary, no preamble.",
        ],
        markdown=False,
        compress_tool_results=True,
        max_tool_calls_from_history=1,
    )


def administrator_agent() -> Agent:
    return Agent(
        name="Book Administrator",
        role="Review the book pipeline with quality checkpoints focused on depth and coherence.",
        model=build_model(),
        instructions=[
            "You are the strict quality gatekeeper for a multi-agent book workflow.",
            f"REJECT any chapter with fewer than {MIN_CHAPTER_WORDS} words — depth is non-negotiable.",
            f"REJECT any blueprint chapter brief whose story_seed is a single sentence — require 3+ sentences.",
            "When reviewing a blueprint: check that every chapter has a multi-sentence story_seed, a narrative_arc,"
            " a verse_reference, and a bridge_to_next that creates narrative tension.",
            "When reviewing chapter drafts: check word count, section completeness, verse integration,"
            " and humor style (must be anecdote, not punchline).",
            "When rejecting, provide SPECIFIC revision notes: name the exact section and exactly what is missing."
            " Do NOT give general feedback like 'improve depth' — say 'Chapter 3 Opening Story needs 2 more paragraphs'.",
            "Approve only when depth targets are met and the content is coherent with the approved blueprint.",
        ],
        markdown=False,
    )


async def run_designer(topic: str, revision_notes: str, jnanalaya: MCPTools, sph: MCPTools) -> BookBlueprint:
    reference_context = await fetch_living_enlightenment_context(jnanalaya)
    verse_context = await fetch_relevant_verse_context(topic, sph, limit=5)
    prompt = dedent(
        f"""\
        Design a book blueprint for the topic: {topic}

        Requirements:
        - Use Living Enlightenment from Kailasa Jnanalaya as the structural and tonal inspiration.
        - Use SPH Books for verse references — one specific verse per chapter.
        - Constrain the plan to {MIN_CHAPTERS}-{MAX_CHAPTERS} chapters.
        - Make the book vivid, practically grounded, humorous in the storytelling sense, and spiritually rich.

        CRITICAL FIELD REQUIREMENTS for each chapter brief:
        - story_seed: Minimum 3 sentences. Describe: WHO is the protagonist (name them), WHERE are they,
          WHAT is the conflict or struggle they face, and WHAT turning point occurs. Not a one-liner.
        - narrative_arc: Minimum 3 sentences. Trace how the teaching insight unfolds across the chapter:
          opening confusion → first insight → deeper understanding → practical realisation.
        - joke_seed: A 2-3 sentence warm storytelling scenario (NOT a punchline joke).
          Think: a self-deprecating story a wise teacher might tell about themselves.
        - bridge_to_next: 2-3 sentences creating narrative tension that will be resolved in the next chapter.
        - target_word_count: 2500 for standard chapters, 3000 for key teaching chapters.

        Prefetched Living Enlightenment context:
        {reference_context}

        Prefetched SPH verse search context:
        {verse_context}

        Revision notes from the administrator:
        {revision_notes or "None. Create the richest possible first-pass blueprint."}
        """
    )
    response = await designer_agent(jnanalaya, sph).arun(prompt, output_schema=BookBlueprint)
    if not isinstance(response.content, BookBlueprint):
        raise RuntimeError("Designer did not return a BookBlueprint.")
    return response.content


async def review_blueprint(topic: str, blueprint: BookBlueprint, heuristic_issues: List[str]) -> AdminReview:
    prompt = dedent(
        f"""\
        Review this book blueprint for the topic: {topic}

        Heuristic issues already detected:
        {json.dumps(heuristic_issues, indent=2) if heuristic_issues else "[]"}

        Blueprint JSON:
        {blueprint.model_dump_json(indent=2)}

        Approve only if the blueprint is ready for chapter writing.
        """
    )
    response = await administrator_agent().arun(prompt, output_schema=AdminReview)
    if not isinstance(response.content, AdminReview):
        raise RuntimeError("Administrator did not return an AdminReview for blueprint.")
    review = response.content
    if heuristic_issues:
        review.approved = False
        review.retry_target = "designer"
        review.issues = list(dict.fromkeys([*heuristic_issues, *review.issues]))
        if not review.revision_notes:
            review.revision_notes = "Fix the structural issues listed and return a compliant blueprint."
    return review


async def write_single_chapter(
    topic: str,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    revision_notes: str,
    jnanalaya: MCPTools,
    sph: MCPTools,
    prior_chapter_summaries: Optional[List[str]] = None,
) -> ChapterDraft:
    chapter_context = await fetch_style_and_verse_for_chapter(chapter_brief, sph)
    prior_context_block = ""
    if prior_chapter_summaries:
        prior_lines = "\n".join(f"  - {s}" for s in prior_chapter_summaries)
        prior_context_block = dedent(
            f"""\
            Previously written chapters (maintain continuity and build on these threads):
            {prior_lines}
            """
        )
    prompt = dedent(
        f"""\
        Write chapter {chapter_brief.number} for a book about: {topic}

        Book-level guidance:
        - Title: {blueprint.book_title}
        - Tone: {blueprint.tone}
        - Speech level: {blueprint.speech_level}
        - Speech style: {blueprint.speech_style}
        - Joke policy: {blueprint.joke_policy}
        - Structure notes: {blueprint.structure_notes}

        Chapter brief:
        {chapter_brief.model_dump_json(indent=2)}

        TARGET: {chapter_brief.target_word_count} words for this chapter.
        Every section MUST have at least {MIN_SECTION_PARAGRAPHS} substantial paragraphs.

        {prior_context_block}
        Revision notes from the administrator:
        {revision_notes or "None. Write the chapter with maximum depth and richness from the approved brief."}

        Prefetched verse/reference context:
        {chapter_context}

        Output markdown with this EXACT section layout (include all five sections):
        ## Chapter {chapter_brief.number}: {chapter_brief.title}
        ### Opening Story
        ### The Teaching
        ### Practical Exercise
        ### Humor
        ### Closing Bridge
        """
    )
    response = await writer_agent(jnanalaya, sph).arun(prompt, output_schema=ChapterDraft)
    if not isinstance(response.content, ChapterDraft):
        raw = str(response.content).strip() if response.content is not None else ""
        if raw:
            return chapter_from_markdown(
                markdown=raw,
                fallback_number=chapter_brief.number,
                fallback_title=chapter_brief.title,
                summary="Recovered from unstructured writer output.",
            )
        raise RuntimeError(f"Writer did not return ChapterDraft for chapter {chapter_brief.number}.")
    return response.content


async def review_draft(
    topic: str,
    blueprint: BookBlueprint,
    chapters: List[ChapterDraft],
    heuristic_issues: List[str],
) -> AdminReview:
    prompt = dedent(
        f"""\
        Review the raw chapter drafts for the topic: {topic}

        Heuristic issues already detected:
        {json.dumps(heuristic_issues, indent=2) if heuristic_issues else "[]"}

        Blueprint JSON:
        {blueprint.model_dump_json(indent=2)}

        Draft summary JSON:
        {json.dumps([chapter.model_dump() for chapter in chapters], indent=2)}

        Approve only if the draft is ready for proofreading.
        If not approved, return revision notes focused on the writer stage.
        """
    )
    response = await administrator_agent().arun(prompt, output_schema=AdminReview)
    if not isinstance(response.content, AdminReview):
        raise RuntimeError("Administrator did not return an AdminReview for draft review.")
    review = response.content
    if heuristic_issues:
        review.approved = False
        review.retry_target = "writer"
        review.issues = list(dict.fromkeys([*heuristic_issues, *review.issues]))
        if not review.revision_notes:
            review.revision_notes = "Revise the failing chapters to satisfy the required structure and chapter brief."
    return review


async def proofread_single_chapter(
    topic: str,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    draft: ChapterDraft,
    revision_notes: str,
    sph: MCPTools,
) -> ChapterDraft:
    chapter_context = await fetch_style_and_verse_for_chapter(chapter_brief, sph)
    prompt = dedent(
        f"""\
        Proofread and deepen chapter {chapter_brief.number} for the topic: {topic}

        Book-level guidance:
        - Tone: {blueprint.tone}
        - Speech level: {blueprint.speech_level}
        - Speech style: {blueprint.speech_style}
        - Joke policy: {blueprint.joke_policy}

        Approved chapter brief:
        {chapter_brief.model_dump_json(indent=2)}

        Target word count: {chapter_brief.target_word_count} words
        Minimum section depth: {MIN_SECTION_PARAGRAPHS} paragraphs per section

        Current chapter draft (markdown):
        {draft.markdown}

        Revision notes from the administrator:
        {revision_notes or "None. Deepen thin sections then polish for final compilation."}

        Prefetched verse/reference context:
        {chapter_context}
        """
    )
    response = await proofreader_agent(sph).arun(prompt, output_schema=ChapterDraft)
    if not isinstance(response.content, ChapterDraft):
        raw = str(response.content).strip() if response.content is not None else ""
        if raw:
            return chapter_from_markdown(
                markdown=raw,
                fallback_number=chapter_brief.number,
                fallback_title=chapter_brief.title,
                summary="Recovered from unstructured proofreader output.",
            )
        raise RuntimeError(f"Proofreader did not return ChapterDraft for chapter {chapter_brief.number}.")
    return response.content


async def review_proofread(
    topic: str,
    blueprint: BookBlueprint,
    chapters: List[ChapterDraft],
    heuristic_issues: List[str],
) -> AdminReview:
    prompt = dedent(
        f"""\
        Review the proofread chapters for the topic: {topic}

        Heuristic issues already detected:
        {json.dumps(heuristic_issues, indent=2) if heuristic_issues else "[]"}

        Blueprint JSON:
        {blueprint.model_dump_json(indent=2)}

        Proofread chapter summary JSON:
        {json.dumps([chapter.model_dump() for chapter in chapters], indent=2)}

        Approve only if this is ready for final compilation.
        If not approved, return revision notes focused on the proofreader stage.
        """
    )
    response = await administrator_agent().arun(prompt, output_schema=AdminReview)
    if not isinstance(response.content, AdminReview):
        raise RuntimeError("Administrator did not return an AdminReview for proofread review.")
    review = response.content
    if heuristic_issues:
        review.approved = False
        review.retry_target = "proofreader"
        review.issues = list(dict.fromkeys([*heuristic_issues, *review.issues]))
        if not review.revision_notes:
            review.revision_notes = "Tighten the proofread chapters without breaking the approved structure."
    return review


async def generate_compiled_metadata(topic: str, blueprint: BookBlueprint, chapters: List[ChapterDraft]) -> CompiledBookMetadata:
    estimated_word_count = compute_word_count(chapters)
    prompt = dedent(
        f"""\
        Compile the final presentation metadata for a generated book.

        Topic: {topic}
        Blueprint:
        {blueprint.model_dump_json(indent=2)}

        Chapter summary:
        {json.dumps([chapter.model_dump() for chapter in chapters], indent=2)}

        Produce:
        - a fitting final title
        - a concise foreword
        - a concise benediction
        - source notes mentioning both MCP sources
        - final chapter count
        - estimated word count around {estimated_word_count}
        """
    )
    response = await administrator_agent().arun(prompt, output_schema=CompiledBookMetadata)
    if not isinstance(response.content, CompiledBookMetadata):
        raise RuntimeError("Administrator did not return CompiledBookMetadata.")
    metadata = response.content
    metadata.chapter_count = len(chapters)
    metadata.estimated_word_count = compute_word_count(chapters, metadata)
    return metadata


async def collect_topic(step_input: StepInput) -> StepOutput:
    topic = step_input.get_input_as_string() or ""
    state = get_session_state(step_input)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ensure_dir(DEFAULT_OUTPUT_ROOT / f"{slugify(topic)}_{timestamp}")
    state["topic"] = topic
    state["output_dir"] = str(output_dir)
    state["artifact_paths"] = {
        "topic": str(output_dir / "topic.json"),
        "blueprint": str(output_dir / "blueprint.md"),
        "chapter_briefs": str(output_dir / "chapter_briefs.json"),
        "draft_dir": str(output_dir / "draft" / "chapters"),
        "proofread_dir": str(output_dir / "proofread" / "chapters"),
        "book": str(output_dir / "book.md"),
        "metadata": str(output_dir / "compiled_metadata.json"),
    }
    write_json(Path(state["artifact_paths"]["topic"]), {"topic": topic, "created_at": timestamp})
    print(f"  Topic captured: {topic}")
    return StepOutput(content={"topic": topic, "output_dir": str(output_dir)})


async def connect_mcp_tools(step_input: StepInput) -> StepOutput:
    runtime = get_runtime(step_input)
    if "jnanalaya" not in runtime:
        print("  Connecting to MCP sources...")
        try:
            runtime["jnanalaya"] = await connect_mcp(JNANALAYA_URL, "Kailasa Jnanalaya MCP")
            runtime["sph"] = await connect_mcp(SPH_BOOKS_URL, "SPH Books MCP")
        except Exception:
            for key in ("jnanalaya", "sph"):
                tool = runtime.pop(key, None)
                if tool is not None:
                    try:
                        await tool.close()
                    except Exception:
                        pass
            raise
    return StepOutput(content={"connected": True, "sources": [JNANALAYA_URL, SPH_BOOKS_URL]})


async def validate_environment(step_input: StepInput) -> StepOutput:
    if not os.getenv("NVIDIA_API_KEY"):
        raise RuntimeError("NVIDIA_API_KEY is not set. Export your build.nvidia.com API key before running the workflow.")
    return StepOutput(content={"nvidia_api_key": "present"})


async def design_book(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    runtime = get_runtime(step_input)
    topic = state["topic"]

    print("  Stage: Designer")
    blueprint = await run_designer(topic, "", runtime["jnanalaya"], runtime["sph"])
    state["blueprint"] = blueprint.model_dump()
    write_text(Path(state["artifact_paths"]["blueprint"]), render_blueprint_markdown(blueprint))
    write_json(Path(state["artifact_paths"]["chapter_briefs"]), [chapter.model_dump() for chapter in blueprint.chapters])
    return StepOutput(content=blueprint)


async def admin_review_blueprint(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    runtime = get_runtime(step_input)
    topic = state["topic"]
    blueprint = BookBlueprint.model_validate(state["blueprint"])

    print("  Stage: Administrator review (blueprint)")
    review: Optional[AdminReview] = None
    for attempt in range(MAX_STAGE_RETRIES + 1):
        heuristic_issues = blueprint_issues(blueprint)
        review = await review_blueprint(topic, blueprint, heuristic_issues)
        if review.approved:
            break
        if attempt >= MAX_STAGE_RETRIES:
            raise RuntimeError(f"Blueprint rejected after retries: {review.model_dump_json(indent=2)}")
        print(f"    Blueprint revision requested (attempt {attempt + 1}/{MAX_STAGE_RETRIES}).")
        blueprint = await run_designer(topic, review.revision_notes, runtime["jnanalaya"], runtime["sph"])

    state["blueprint"] = blueprint.model_dump()
    state["blueprint_review"] = review.model_dump() if review is not None else None
    write_text(Path(state["artifact_paths"]["blueprint"]), render_blueprint_markdown(blueprint))
    write_json(Path(state["artifact_paths"]["chapter_briefs"]), [chapter.model_dump() for chapter in blueprint.chapters])
    return StepOutput(content={"blueprint": blueprint.model_dump(), "review": review.model_dump() if review else None})


async def write_chapters_loop(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    runtime = get_runtime(step_input)
    topic = state["topic"]
    blueprint = BookBlueprint.model_validate(state["blueprint"])
    chapters: List[ChapterDraft] = []
    prior_summaries: List[str] = []  # rolling list for narrative continuity

    print("  Stage: Writer")
    draft_dir = ensure_dir(Path(state["artifact_paths"]["draft_dir"]))
    for chapter_brief in blueprint.chapters:
        print(f"    Writing chapter {chapter_brief.number}/{blueprint.chapter_count} (target {chapter_brief.target_word_count} words)...")
        draft = await write_single_chapter(
            topic=topic,
            blueprint=blueprint,
            chapter_brief=chapter_brief,
            revision_notes="",
            jnanalaya=runtime["jnanalaya"],
            sph=runtime["sph"],
            prior_chapter_summaries=prior_summaries if chapter_brief.number > 1 else None,
        )
        chapters.append(draft)
        prior_summaries.append(f"Ch {chapter_brief.number} '{draft.title}': {draft.summary}")
        write_text(draft_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", draft.markdown)
        print(f"      → {draft.word_count} words written.")
        await asyncio.sleep(1)

    state["drafts"] = [chapter.model_dump() for chapter in chapters]
    return StepOutput(content=[chapter.model_dump() for chapter in chapters])


async def admin_review_draft(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    runtime = get_runtime(step_input)
    topic = state["topic"]
    blueprint = BookBlueprint.model_validate(state["blueprint"])
    chapters = [ChapterDraft.model_validate(item) for item in state.get("drafts", [])]
    draft_dir = ensure_dir(Path(state["artifact_paths"]["draft_dir"]))

    print("  Stage: Administrator review (draft)")
    review: Optional[AdminReview] = None
    for attempt in range(MAX_STAGE_RETRIES + 1):
        heuristic_issues = chapter_list_issues(chapters, blueprint)
        review = await review_draft(topic, blueprint, chapters, heuristic_issues)
        if review.approved:
            break
        if attempt >= MAX_STAGE_RETRIES:
            raise RuntimeError(f"Draft rejected after retries: {review.model_dump_json(indent=2)}")
        print(f"    Draft revision requested (attempt {attempt + 1}/{MAX_STAGE_RETRIES}).")
        revised_chapters: List[ChapterDraft] = []
        for chapter_brief in blueprint.chapters:
            existing = chapters[chapter_brief.number - 1]
            issues_for_chapter = chapter_issues(existing, chapter_brief.number, chapter_brief.title)
            needs_revision = bool(issues_for_chapter) or "chapter" in review.revision_notes.lower()
            if needs_revision:
                revised = await write_single_chapter(
                    topic=topic,
                    blueprint=blueprint,
                    chapter_brief=chapter_brief,
                    revision_notes=review.revision_notes,
                    jnanalaya=runtime["jnanalaya"],
                    sph=runtime["sph"],
                )
                revised_chapters.append(revised)
                write_text(draft_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", revised.markdown)
                await asyncio.sleep(1)
            else:
                revised_chapters.append(existing)
        chapters = revised_chapters

    state["drafts"] = [chapter.model_dump() for chapter in chapters]
    state["draft_review"] = review.model_dump() if review is not None else None
    return StepOutput(content={"drafts": state["drafts"], "review": review.model_dump() if review else None})


async def proofread_chapters_loop(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    runtime = get_runtime(step_input)
    topic = state["topic"]
    blueprint = BookBlueprint.model_validate(state["blueprint"])
    drafts = [ChapterDraft.model_validate(item) for item in state.get("drafts", [])]
    proofread_dir = ensure_dir(Path(state["artifact_paths"]["proofread_dir"]))
    polished: List[ChapterDraft] = []

    print("  Stage: Proofreader")
    for chapter_brief, draft in zip(blueprint.chapters, drafts):
        print(f"    Proofreading chapter {chapter_brief.number}/{blueprint.chapter_count}...")
        polished_chapter = await proofread_single_chapter(
            topic=topic,
            blueprint=blueprint,
            chapter_brief=chapter_brief,
            draft=draft,
            revision_notes="",
            sph=runtime["sph"],
        )
        polished.append(polished_chapter)
        write_text(proofread_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", polished_chapter.markdown)
        await asyncio.sleep(1)

    state["proofread"] = [chapter.model_dump() for chapter in polished]
    return StepOutput(content=state["proofread"])


async def admin_finalize_book(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    runtime = get_runtime(step_input)
    topic = state["topic"]
    blueprint = BookBlueprint.model_validate(state["blueprint"])
    chapters = [ChapterDraft.model_validate(item) for item in state.get("proofread", [])]
    proofread_dir = ensure_dir(Path(state["artifact_paths"]["proofread_dir"]))

    print("  Stage: Administrator final review and compilation")
    review: Optional[AdminReview] = None
    for attempt in range(MAX_STAGE_RETRIES + 1):
        heuristic_issues = chapter_list_issues(chapters, blueprint)
        review = await review_proofread(topic, blueprint, chapters, heuristic_issues)
        if review.approved:
            break
        if attempt >= MAX_STAGE_RETRIES:
            raise RuntimeError(f"Proofread draft rejected after retries: {review.model_dump_json(indent=2)}")
        print(f"    Proofreader revision requested (attempt {attempt + 1}/{MAX_STAGE_RETRIES}).")
        revised: List[ChapterDraft] = []
        for chapter_brief, current in zip(blueprint.chapters, chapters):
            refreshed = await proofread_single_chapter(
                topic=topic,
                blueprint=blueprint,
                chapter_brief=chapter_brief,
                draft=current,
                revision_notes=review.revision_notes,
                sph=runtime["sph"],
            )
            revised.append(refreshed)
            write_text(proofread_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", refreshed.markdown)
            await asyncio.sleep(1)
        chapters = revised

    metadata = await generate_compiled_metadata(topic, blueprint, chapters)
    final_book = assemble_book(metadata, chapters)
    state["proofread"] = [chapter.model_dump() for chapter in chapters]
    state["final_review"] = review.model_dump() if review is not None else None
    state["compiled_metadata"] = metadata.model_dump()
    state["final_book"] = final_book
    return StepOutput(content={"metadata": metadata.model_dump(), "book": final_book})


async def save_outputs(step_input: StepInput) -> StepOutput:
    state = get_session_state(step_input)
    metadata = CompiledBookMetadata.model_validate(state["compiled_metadata"])
    final_book = state["final_book"]
    write_json(Path(state["artifact_paths"]["metadata"]), metadata.model_dump())
    write_text(Path(state["artifact_paths"]["book"]), final_book)
    print(f"  Saved final book to: {state['artifact_paths']['book']}")
    return StepOutput(
        content={
            "book_path": state["artifact_paths"]["book"],
            "metadata_path": state["artifact_paths"]["metadata"],
            "chapter_count": metadata.chapter_count,
            "estimated_word_count": metadata.estimated_word_count,
        }
    )


@dataclass
class BookWorkflowRuntime:
    jnanalaya: Optional[MCPTools] = None
    sph: Optional[MCPTools] = None

    async def connect(self) -> None:
        if self.jnanalaya is None:
            self.jnanalaya = await connect_mcp(JNANALAYA_URL, "Kailasa Jnanalaya MCP")
        if self.sph is None:
            self.sph = await connect_mcp(SPH_BOOKS_URL, "SPH Books MCP")

    async def close(self) -> None:
        for tool in (self.jnanalaya, self.sph):
            if tool is not None:
                try:
                    await tool.close()
                except Exception:
                    pass
        self.jnanalaya = None
        self.sph = None


def bundle_from_step_input(step_input: StepInput) -> Dict[str, Any]:
    content = step_input.get_last_step_content()
    if not isinstance(content, dict):
        raise RuntimeError("Workflow step did not receive the expected bundle payload.")
    return dict(content)


class CollectTopicExecutor:
    def __call__(self, step_input: StepInput) -> StepOutput:
        topic = step_input.get_input_as_string() or ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = ensure_dir(DEFAULT_OUTPUT_ROOT / f"{slugify(topic)}_{timestamp}")
        artifact_paths = {
            "topic": str(output_dir / "topic.json"),
            "blueprint": str(output_dir / "blueprint.md"),
            "chapter_briefs": str(output_dir / "chapter_briefs.json"),
            "draft_dir": str(output_dir / "draft" / "chapters"),
            "proofread_dir": str(output_dir / "proofread" / "chapters"),
            "book": str(output_dir / "book.md"),
            "metadata": str(output_dir / "compiled_metadata.json"),
        }
        write_json(Path(artifact_paths["topic"]), {"topic": topic, "created_at": timestamp})
        print(f"  Topic captured: {topic}")
        return StepOutput(content={"topic": topic, "output_dir": str(output_dir), "artifact_paths": artifact_paths})


class ValidateEnvironmentExecutor:
    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        if not os.getenv("NVIDIA_API_KEY"):
            raise RuntimeError("NVIDIA_API_KEY is not set. Export your build.nvidia.com API key before running the workflow.")
        bundle["environment"] = {"nvidia_api_key": "present"}
        return StepOutput(content=bundle)


class ValidateModelAccessExecutor:
    async def __call__(self, step_input: StepInput) -> StepOutput:
        global ACTIVE_NVIDIA_MODEL_ID
        bundle = bundle_from_step_input(step_input)
        seen: List[str] = []
        last_error = "unknown error"
        for candidate in MODEL_CANDIDATES:
            if candidate in seen:
                continue
            seen.append(candidate)
            probe_agent = Agent(model=Nvidia(id=candidate, max_tokens=MAX_AGENT_OUTPUT_TOKENS), markdown=False)
            response = await probe_agent.arun("Reply with exactly OK.")
            if response.status == RunStatus.error:
                provider_detail = response.model_provider_data or {}
                last_error = str(provider_detail or response.content or "provider error")
                continue
            content = str(response.content).strip() if response.content is not None else ""
            if content:
                ACTIVE_NVIDIA_MODEL_ID = candidate
                bundle["model"] = {"id": candidate, "probe_response": content}
                return StepOutput(content=bundle)
        raise RuntimeError(
            "NVIDIA model validation failed for all candidates. "
            f"Tried: {', '.join(seen)}. Last error: {last_error}"
        )


class ConnectMcpExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        print("  Connecting to MCP sources...")
        await self.runtime.connect()
        bundle["mcp"] = {"connected": True, "sources": [JNANALAYA_URL, SPH_BOOKS_URL]}
        return StepOutput(content=bundle)


class DesignBookExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        print("  Stage: Designer")
        blueprint = await run_designer(bundle["topic"], "", self.runtime.jnanalaya, self.runtime.sph)
        bundle["blueprint"] = blueprint.model_dump()
        write_text(Path(bundle["artifact_paths"]["blueprint"]), render_blueprint_markdown(blueprint))
        write_json(Path(bundle["artifact_paths"]["chapter_briefs"]), [chapter.model_dump() for chapter in blueprint.chapters])
        return StepOutput(content=bundle)


class ReviewBlueprintExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        blueprint = BookBlueprint.model_validate(bundle["blueprint"])
        print("  Stage: Administrator review (blueprint)")
        review: Optional[AdminReview] = None
        for attempt in range(MAX_STAGE_RETRIES + 1):
            heuristic_issues = blueprint_issues(blueprint)
            review = await review_blueprint(bundle["topic"], blueprint, heuristic_issues)
            if review.approved:
                break
            if attempt >= MAX_STAGE_RETRIES:
                raise RuntimeError(f"Blueprint rejected after retries: {review.model_dump_json(indent=2)}")
            print(f"    Blueprint revision requested (attempt {attempt + 1}/{MAX_STAGE_RETRIES}).")
            blueprint = await run_designer(bundle["topic"], review.revision_notes, self.runtime.jnanalaya, self.runtime.sph)
        bundle["blueprint"] = blueprint.model_dump()
        bundle["blueprint_review"] = review.model_dump() if review else None
        write_text(Path(bundle["artifact_paths"]["blueprint"]), render_blueprint_markdown(blueprint))
        write_json(Path(bundle["artifact_paths"]["chapter_briefs"]), [chapter.model_dump() for chapter in blueprint.chapters])
        return StepOutput(content=bundle)


class WriteChaptersExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        blueprint = BookBlueprint.model_validate(bundle["blueprint"])
        drafts: List[ChapterDraft] = []
        prior_summaries: List[str] = []  # rolling list for narrative continuity
        print("  Stage: Writer")
        draft_dir = ensure_dir(Path(bundle["artifact_paths"]["draft_dir"]))
        for chapter_brief in blueprint.chapters:
            print(f"    Writing chapter {chapter_brief.number}/{blueprint.chapter_count} (target {chapter_brief.target_word_count} words)...")
            draft = await write_single_chapter(
                topic=bundle["topic"],
                blueprint=blueprint,
                chapter_brief=chapter_brief,
                revision_notes="",
                jnanalaya=self.runtime.jnanalaya,
                sph=self.runtime.sph,
                prior_chapter_summaries=prior_summaries if chapter_brief.number > 1 else None,
            )
            drafts.append(draft)
            prior_summaries.append(f"Ch {chapter_brief.number} '{draft.title}': {draft.summary}")
            write_text(draft_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", draft.markdown)
            print(f"      → {draft.word_count} words written.")
            await asyncio.sleep(1)
        bundle["drafts"] = [chapter.model_dump() for chapter in drafts]
        return StepOutput(content=bundle)


class ReviewDraftExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        blueprint = BookBlueprint.model_validate(bundle["blueprint"])
        chapters = [ChapterDraft.model_validate(item) for item in bundle.get("drafts", [])]
        draft_dir = ensure_dir(Path(bundle["artifact_paths"]["draft_dir"]))
        print("  Stage: Administrator review (draft)")
        review: Optional[AdminReview] = None
        for attempt in range(MAX_STAGE_RETRIES + 1):
            heuristic_issues = chapter_list_issues(chapters, blueprint)
            review = await review_draft(bundle["topic"], blueprint, chapters, heuristic_issues)
            if review.approved:
                break
            if attempt >= MAX_STAGE_RETRIES:
                raise RuntimeError(f"Draft rejected after retries: {review.model_dump_json(indent=2)}")
            print(f"    Draft revision requested (attempt {attempt + 1}/{MAX_STAGE_RETRIES}).")
            revised_chapters: List[ChapterDraft] = []
            for chapter_brief in blueprint.chapters:
                existing = chapters[chapter_brief.number - 1]
                issues_for_chapter = chapter_issues(existing, chapter_brief.number, chapter_brief.title)
                needs_revision = bool(issues_for_chapter) or review.retry_target == "writer"
                if needs_revision:
                    revised = await write_single_chapter(
                        topic=bundle["topic"],
                        blueprint=blueprint,
                        chapter_brief=chapter_brief,
                        revision_notes=review.revision_notes,
                        jnanalaya=self.runtime.jnanalaya,
                        sph=self.runtime.sph,
                    )
                    revised_chapters.append(revised)
                    write_text(draft_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", revised.markdown)
                    await asyncio.sleep(1)
                else:
                    revised_chapters.append(existing)
            chapters = revised_chapters
        bundle["drafts"] = [chapter.model_dump() for chapter in chapters]
        bundle["draft_review"] = review.model_dump() if review else None
        return StepOutput(content=bundle)


class ProofreadChaptersExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        blueprint = BookBlueprint.model_validate(bundle["blueprint"])
        drafts = [ChapterDraft.model_validate(item) for item in bundle.get("drafts", [])]
        proofread_dir = ensure_dir(Path(bundle["artifact_paths"]["proofread_dir"]))
        polished: List[ChapterDraft] = []
        print("  Stage: Proofreader")
        for chapter_brief, draft in zip(blueprint.chapters, drafts):
            print(f"    Proofreading chapter {chapter_brief.number}/{blueprint.chapter_count}...")
            polished_chapter = await proofread_single_chapter(
                topic=bundle["topic"],
                blueprint=blueprint,
                chapter_brief=chapter_brief,
                draft=draft,
                revision_notes="",
                sph=self.runtime.sph,
            )
            polished.append(polished_chapter)
            write_text(proofread_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", polished_chapter.markdown)
            await asyncio.sleep(1)
        bundle["proofread"] = [chapter.model_dump() for chapter in polished]
        return StepOutput(content=bundle)


class FinalizeBookExecutor:
    def __init__(self, runtime: BookWorkflowRuntime):
        self.runtime = runtime

    async def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        blueprint = BookBlueprint.model_validate(bundle["blueprint"])
        chapters = [ChapterDraft.model_validate(item) for item in bundle.get("proofread", [])]
        proofread_dir = ensure_dir(Path(bundle["artifact_paths"]["proofread_dir"]))
        print("  Stage: Administrator final review and compilation")
        review: Optional[AdminReview] = None
        for attempt in range(MAX_STAGE_RETRIES + 1):
            heuristic_issues = chapter_list_issues(chapters, blueprint)
            review = await review_proofread(bundle["topic"], blueprint, chapters, heuristic_issues)
            if review.approved:
                break
            if attempt >= MAX_STAGE_RETRIES:
                raise RuntimeError(f"Proofread draft rejected after retries: {review.model_dump_json(indent=2)}")
            print(f"    Proofreader revision requested (attempt {attempt + 1}/{MAX_STAGE_RETRIES}).")
            revised: List[ChapterDraft] = []
            for chapter_brief, current in zip(blueprint.chapters, chapters):
                refreshed = await proofread_single_chapter(
                    topic=bundle["topic"],
                    blueprint=blueprint,
                    chapter_brief=chapter_brief,
                    draft=current,
                    revision_notes=review.revision_notes,
                    sph=self.runtime.sph,
                )
                revised.append(refreshed)
                write_text(proofread_dir / f"{chapter_brief.number:02d}_{slugify(chapter_brief.title)}.md", refreshed.markdown)
                await asyncio.sleep(1)
            chapters = revised
        metadata = await generate_compiled_metadata(bundle["topic"], blueprint, chapters)
        final_book = assemble_book(metadata, chapters)
        bundle["proofread"] = [chapter.model_dump() for chapter in chapters]
        bundle["final_review"] = review.model_dump() if review else None
        bundle["compiled_metadata"] = metadata.model_dump()
        bundle["final_book"] = final_book
        return StepOutput(content=bundle)


class SaveOutputsExecutor:
    def __call__(self, step_input: StepInput) -> StepOutput:
        bundle = bundle_from_step_input(step_input)
        metadata = CompiledBookMetadata.model_validate(bundle["compiled_metadata"])
        write_json(Path(bundle["artifact_paths"]["metadata"]), metadata.model_dump())
        write_text(Path(bundle["artifact_paths"]["book"]), bundle["final_book"])
        print(f"  Saved final book to: {bundle['artifact_paths']['book']}")
        return StepOutput(
            content={
                "book_path": bundle["artifact_paths"]["book"],
                "metadata_path": bundle["artifact_paths"]["metadata"],
                "chapter_count": metadata.chapter_count,
                "estimated_word_count": metadata.estimated_word_count,
                "model_id": NVIDIA_MODEL_ID,
            }
        )


def build_workflow(runtime: BookWorkflowRuntime) -> Workflow:
    return Workflow(
        name="Agno Multi-Agent Book Generator",
        description="Workflow-driven multi-agent book generation with administrator checkpoints.",
        steps=[
            Step(name="collect_topic", executor=CollectTopicExecutor(), on_error=OnError.fail),
            Step(name="validate_environment", executor=ValidateEnvironmentExecutor(), on_error=OnError.fail),
            Step(name="validate_model_access", executor=ValidateModelAccessExecutor(), on_error=OnError.fail),
            Step(name="connect_mcp_tools", executor=ConnectMcpExecutor(runtime), on_error=OnError.fail),
            Step(name="design_book", executor=DesignBookExecutor(runtime), on_error=OnError.fail),
            Step(name="admin_review_blueprint", executor=ReviewBlueprintExecutor(runtime), on_error=OnError.fail),
            Step(name="write_chapters_loop", executor=WriteChaptersExecutor(runtime), on_error=OnError.fail),
            Step(name="admin_review_draft", executor=ReviewDraftExecutor(runtime), on_error=OnError.fail),
            Step(name="proofread_chapters_loop", executor=ProofreadChaptersExecutor(runtime), on_error=OnError.fail),
            Step(name="admin_finalize_book", executor=FinalizeBookExecutor(runtime), on_error=OnError.fail),
            Step(name="save_outputs", executor=SaveOutputsExecutor(), on_error=OnError.fail),
        ],
        stream=False,
        debug_mode=False,
        store_events=False,
        telemetry=False,
    )


async def run_workflow(topic: str) -> WorkflowRunOutput:
    runtime = BookWorkflowRuntime()
    workflow = build_workflow(runtime)
    try:
        result = await workflow.arun(input=topic)
        if not isinstance(result, WorkflowRunOutput):
            raise RuntimeError("Workflow did not return a WorkflowRunOutput.")
        return result
    finally:
        await runtime.close()


async def run_default_pipeline(topic: str) -> Optional[Path]:
    import book_workflow

    book_workflow.NVIDIA_MODEL_ID = ACTIVE_NVIDIA_MODEL_ID
    await book_workflow.run_pipeline(topic)
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    matches = sorted(output_dir.glob("*_book.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def recover_book_from_latest_drafts(topic: str) -> Optional[Path]:
    base = Path("output")
    candidates = sorted(
        [path for path in base.iterdir() if path.is_dir() and slugify(topic) in path.name.lower()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for run_dir in candidates:
        draft_dir = run_dir / "draft" / "chapters"
        chapter_files = sorted(draft_dir.glob("*.md"))
        if not chapter_files:
            continue
        chapters = []
        for index, path in enumerate(chapter_files, 1):
            text = path.read_text(encoding="utf-8")
            chapters.append(
                chapter_from_markdown(
                    markdown=text,
                    fallback_number=index,
                    fallback_title=path.stem,
                    summary="Recovered from latest draft artifacts.",
                )
            )
        title = "Recovered Book"
        blueprint_path = run_dir / "blueprint.md"
        if blueprint_path.exists():
            for line in blueprint_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        metadata = CompiledBookMetadata(
            topic=topic,
            title=title,
            foreword="This recovered edition compiles the latest completed draft chapters into a single readable manuscript.",
            benediction="May this inquiry return you to the witness behind every thought, sensation, and identity.",
            source_notes=[
                "Kailasa Jnanalaya MCP for Living Enlightenment-inspired structure and tone.",
                "SPH Books MCP for verse-search context and spiritual reference material.",
            ],
            chapter_count=len(chapters),
            estimated_word_count=1,
        )
        metadata.estimated_word_count = compute_word_count(chapters, metadata)
        book = assemble_book(metadata, chapters)
        recovered_path = run_dir / "book_recovered.md"
        recovered_path.write_text(book, encoding="utf-8")
        root_copy = base / f"{slugify(topic)}_recovered_book.md"
        root_copy.write_text(book, encoding="utf-8")
        return root_copy
    return None


async def async_main() -> None:
    topic = ask_topic()
    try:
        result = await run_workflow(topic)
        content = result.content if isinstance(result, WorkflowRunOutput) else None
        if isinstance(content, dict):
            print()
            print("=" * 72)
            print("  Book generation complete")
            print("=" * 72)
            print(f"  Book: {content.get('book_path')}")
            print(f"  Metadata: {content.get('metadata_path')}")
            print(f"  Chapters: {content.get('chapter_count')}")
            print(f"  Estimated words: {content.get('estimated_word_count')}")
            print(f"  Model: {content.get('model_id')}")
            print("=" * 72)
            print()
    except Exception as exc:
        print()
        print("  Workflow path failed. Falling back to default sequential generator...")
        print(f"  Reason: {exc}")
        print()
        fallback_path: Optional[Path] = None
        try:
            fallback_path = await run_default_pipeline(topic)
        except Exception as fallback_exc:
            print(f"  Default pipeline also failed: {fallback_exc}")
        if fallback_path is None:
            fallback_path = recover_book_from_latest_drafts(topic)
        if fallback_path is not None:
            print("=" * 72)
            print("  Book recovered from available generation artifacts")
            print("=" * 72)
            print(f"  Book: {fallback_path.resolve()}")
            print("=" * 72)
            print()
        else:
            raise


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
