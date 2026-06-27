"""
Agent definitions for the book generation pipeline.

Each agent is a factory function that returns an Agno Agent
configured with the right model, instructions, and tools.
"""

from __future__ import annotations

from textwrap import dedent
from typing import Any, List, Optional

from agno.agent import Agent

from config import AppConfig, build_agent_model, load_config
from models import (
    BookBlueprint,
    BookConfig,
    ChapterBrief,
    ChapterDraft,
    EditedChapter,
    ResearchPacket,
)


def _cfg() -> AppConfig:
    return load_config()


# ── Voice Profile ──────────────────────────────────────────────────────────

SWAMIJI_VOICE = dedent("""\
    AUTHOR VOICE & IDENTITY:
    The book is written in first person by The SPH Bhagwan Sri Nithyananda Paramashivam,
    referred to by devotees as "Swamiji". Write AS Swamiji, not ABOUT Swamiji.

    TONE CHARACTERISTICS (from Living Enlightenment and other works by Swamiji):
    - Direct transmission of Guruvaak — speak with absolute spiritual authority,
      not as opinion or suggestion but as lived truth and cosmic declaration.
    - Fierce, protective compassion for Sanatana Hindu Dharma — the teachings defend,
      preserve, and expand the authentic Vedic-Agamic tradition.
    - Use vivid, earthy metaphors drawn from daily life — cooking, driving, relationships,
      the body — to make the highest truths accessible.
    - Address the reader directly and intimately: "Understand...", "Listen...",
      "I tell you...", "Let me tell you a story...", "See..."
    - Weave between storytelling, direct instruction, and shastric authority seamlessly.
    - Use Sanskrit/Tamil terms naturally with immediate English context
      (e.g. "your ahamkara, your ego identity", "chitta, the inner space of your being").
    - Humor is warm, self-deprecating, and arises from real-life incidents —
      stories about devotees, ashram life, childhood incidents, or the guru's own journey.
    - The voice is never dry or academic — it is alive, pulsing, and carries
      the energy of a live satsang (spiritual discourse).
    - Frequently reference Paramashiva, Sadashiva, Vedas, Agamas, Upanishads as
      living authorities, not historical curiosities.
    - Key phrases natural to Swamiji: "Understand", "I tell you", "Beautifully",
      "This is what I call...", "The science is...", "Paramashiva reveals in the Agama...",
      "In Sanatana Hindu Dharma, we say..."
""")


# ── 1. Intake Agent ────────────────────────────────────────────────────────

def intake_agent(config: Optional[AppConfig] = None) -> Agent:
    """Validates and enriches raw user input into a BookConfig."""
    return Agent(
        name="Intake Agent",
        role="Validate and enrich book configuration from user input.",
        model=build_agent_model("intake", config),
        instructions=[
            "You receive raw user input describing a book they want to generate.",
            "Your job is to produce a complete, validated BookConfig.",
            "If the user omitted optional fields, fill in sensible defaults based on context.",
            "If required fields are missing, infer them from the synopsis and themes.",
            "Do NOT ask follow-up questions — make your best judgment.",
            "Output a valid BookConfig JSON object.",
        ],
        markdown=False,
    )


# ── 2. Architect Agent ─────────────────────────────────────────────────────

def architect_agent(
    book_config: BookConfig,
    tools: Optional[List[Any]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Designs the book blueprint from a validated BookConfig."""
    cfg = config or _cfg()
    wf = cfg.workflow

    instructions = [
        "You are a book architect for a published spiritual book.",
        "Design a detailed, properly structured blueprint — not a list of flat chapters,",
        "but a real book with named sections, a preface, introduction, and conclusion.",
        "",
        SWAMIJI_VOICE,
        "",
        f"The book has {book_config.num_chapters} chapters, each targeting ~{book_config.words_per_chapter} words.",
        f"POV: {book_config.pov} | Tone: {book_config.tone} | Reading level: {book_config.reading_level}",
        f"Language: {book_config.language}",
        "",
        "Synopsis:",
        book_config.synopsis,
        "",
        f"Themes: {', '.join(book_config.themes)}",
        f"Target audience: {book_config.target_audience}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "BOOK STRUCTURE — assign chapter_type and section_group to every chapter:",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Chapter 1    → chapter_type: 'preface'       target_word_count: {cfg.workflow.preface_words}",
        "               Title: evocative, e.g. 'Before You Begin' or 'A Note to the Reader'",
        "               No opening story, no exercise — Swamiji speaks directly to the reader.",
        "               section_group: '' (no section divider for preface)",
        "",
        "Chapter 2    → chapter_type: 'introduction'",
        "               Full chapter — sets the book's central question, why it matters now.",
        "               section_group: '' (no section divider)",
        "",
        "Chapters 3-4 → chapter_type: 'preliminary'",
        "               section_group: 'Part I: [evocative name]'",
        "               Foundational concepts — clears confusion, builds the vocabulary.",
        "",
        "Chapters 5 to N-1 → chapter_type: 'main'",
        "               section_group: 'Part II: [evocative name]' (or split into Part II + Part III)",
        "               Core teachings — the deep dives.",
        "",
        f"Chapter N    → chapter_type: 'conclusion'    target_word_count: {cfg.workflow.conclusion_words}",
        "               section_group: 'Part III: [evocative name]' or standalone",
        "               Synthesis — sends the reader back into life transformed.",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "CHAPTER TITLE STYLE — titles must read like a published spiritual book:",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "  - 4-8 words, evocative not descriptive",
        "  - First word often a noun or 'The'",
        "  - DO NOT: 'Understanding Consciousness', 'The Nature of Awareness'",
        "  - DO: 'The Fire That Does Not Burn', 'Before the First Thought',",
        "         'The Mirror Has No Dust', 'Living on the Edge of Forever'",
        "  - Models: Eckhart Tolle, Ramana Maharshi, Living Enlightenment chapter titles",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "SECTION GROUP LABELS — name each Part like a book subtitle:",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "  - Format: 'Part I: The Ground of Being'",
        "  - The subtitle after the colon must be evocative, not a topic label",
        "  - Examples: 'Part I: Clearing the Smoke', 'Part II: The Awakening Fire',",
        "              'Part III: Living the Truth'",
        "",
        "Section template for each chapter: " + " -> ".join(book_config.section_template),
        "",
        "For EACH chapter brief you MUST provide:",
        "  - title: compelling, published-book style (see title style guide above)",
        "  - chapter_type: one of 'preface' | 'introduction' | 'preliminary' | 'main' | 'conclusion'",
        "  - section_group: the Part label (e.g. 'Part I: The Ground of Being') or '' for preface/intro",
        "  - synopsis: 2-3 sentences on what this chapter covers",
        "  - story_seed: AT LEAST 3 sentences — protagonist, setting, conflict, turning point",
        "    (For preface: 'none' — preface has no story)",
        "  - narrative_arc: 3-5 sentences tracing the insight progression",
        "  - teaching_points: list of key points this chapter teaches",
        "  - verse_references: exact shastra references — include the original Sanskrit verse/shloka/sutra",
        "    along with its source (e.g. 'Bhagavad Gita 2.47', 'Patanjali Yoga Sutra 1.2', 'Vivekachudamani 20').",
        "  - humor_seed: 2-3 sentence warm anecdote scenario (NOT a punchline)",
        "  - bridge_to_next: 2-3 sentences forming a narrative hook into the next chapter",
        f"  - target_word_count: default {book_config.words_per_chapter}; preface={cfg.workflow.preface_words}; conclusion={cfg.workflow.conclusion_words}",
        "",
        "Also provide:",
        "  - sections: list of BookSectionGroup objects — one per Part (not for preface/intro)",
        "    Each has: label (e.g. 'Part I: The Ground of Being'), chapter_numbers, description",
        "  - thematic_arc: how the reader transforms from preface to conclusion",
        "  - recurring_motifs: images/phrases that repeat for cohesion",
        "  - voice_notes: guidance for the Writer on tone and speech patterns",
    ]

    if book_config.chapter_titles:
        instructions.append("")
        instructions.append("User-specified chapter titles (use these exactly):")
        for i, t in enumerate(book_config.chapter_titles, 1):
            instructions.append(f"  Chapter {i}: {t}")

    if tools:
        instructions.extend([
            "",
            "AVAILABLE MCP TOOLS (use EXACT names):",
            "  Jnanalaya: search-books, resolve-book, list-books, get-chapters, read-chapter, search-sections",
            "  SPH Books: search_chapters, list_chapters, get_chapter, get_book, list_books",
            "You may optionally call 1-2 tools to find structural inspiration. Keep tool use minimal.",
        ])

    return Agent(
        name="Architect Agent",
        role="Design a richly detailed book blueprint.",
        model=build_agent_model("architect", config),
        instructions=instructions,
        tools=tools or [],
        markdown=False,
        tool_call_limit=5,
    )


# ── 3. Researcher Agent ────────────────────────────────────────────────────

def researcher_agent(
    book_config: BookConfig,
    chapter_brief: ChapterBrief,
    tools: Optional[List[Any]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Gathers source material for a single chapter."""

    # Build compact search instructions — keep it short to save tokens
    verse_list = ", ".join(chapter_brief.verse_references) if chapter_brief.verse_references else "find relevant Vedic/Agamic verses"
    topics = ", ".join(chapter_brief.teaching_points[:3])

    return Agent(
        name=f"Researcher (Ch.{chapter_brief.chapter_number})",
        role=f"Gather source material for chapter {chapter_brief.chapter_number}: {chapter_brief.title}",
        model=build_agent_model("researcher", config),
        instructions=[
            f"Research chapter {chapter_brief.chapter_number}: '{chapter_brief.title}'.",
            f"Topics: {topics}",
            f"Verses needed: {verse_list}",
            "",
            "CRITICAL — TOOL NAME RULES:",
            "  HYPHENS for Jnanalaya: search-books  resolve-book  list-books  get-chapters  read-chapter",
            "  UNDERSCORES for SPH:    search_chapters  list_chapters  get_chapter  get_book  list_books",
            "  DO NOT MIX: search_books is WRONG. search-books is RIGHT for Jnanalaya.",
            "  DO NOT MIX: search-chapters is WRONG. search_chapters is RIGHT for SPH.",
            "  If a call fails, SKIP IT — do not retry.",
            "",
            "Strategy: call search_chapters(query='<topic>') on SPH, limit to 3 calls total.",
            "",
            "For each quote, include: Sanskrit text, exact source, English translation.",
            "",
            "SOURCE LINK EXTRACTION — IMPORTANT:",
            "  Transcripts from MCP tools often contain YouTube URLs (youtube.com/watch or youtu.be).",
            "  Whenever a tool response contains a YouTube link, extract it into source_links.",
            "  For each link capture:",
            "    - title: the satsang/video title from the transcript metadata",
            "    - url: the full YouTube URL",
            "    - date: the date of the satsang if present (e.g. '14 Mar 2019')",
            f"    - chapter_number: {chapter_brief.chapter_number}",
            "  If no YouTube links appear in the tool responses, leave source_links empty.",
            "",
            "Output a ResearchPacket including source_links. Do NOT write prose.",
        ],
        tools=tools or [],
        markdown=False,
        tool_call_limit=5,
    )


# ── 4. Writer Agents (3-agent pipeline per chapter) ────────────────────────
#
# 4a. Content Writer  — teaching, exercise, humor, bridge
# 4b. Story Writer    — opening story (Living Enlightenment style)
# 4c. Combiner Writer — merges both into final chapter
#

def _build_prior_context(prior_summaries: Optional[List[str]]) -> str:
    if not prior_summaries:
        return ""
    lines = "\n".join(f"  - {s}" for s in prior_summaries)
    return f"\nPreviously written chapters (maintain continuity):\n{lines}\n"


def _build_research_context(research: Optional[ResearchPacket]) -> str:
    if not research:
        return ""
    parts = []
    for q in research.quotes:
        parts.append(f"  Quote: \"{q.get('text', '')}\" — {q.get('source', 'unknown')}")
    for fact in research.key_facts:
        parts.append(f"  Fact: {fact}")
    for anec in research.anecdotes:
        parts.append(f"  Anecdote: {anec}")
    return "\nResearch material:\n" + "\n".join(parts) + "\n" if parts else ""


def content_writer_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    research: Optional[ResearchPacket] = None,
    prior_summaries: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Writes the teaching, practical exercise, humor, and closing bridge."""
    cfg = config or _cfg()
    wf = cfg.workflow

    # Only the non-story sections
    content_sections = [s for s in book_config.section_template if s != "opening_story"]
    section_instructions = _build_section_instructions(content_sections, wf)
    prior_context = _build_prior_context(prior_summaries)
    research_context = _build_research_context(research)

    return Agent(
        name=f"ContentWriter (Ch.{chapter_brief.chapter_number})",
        role=f"Write teaching content for chapter {chapter_brief.chapter_number}: {chapter_brief.title}",
        model=build_agent_model("writer", config),
        instructions=[
            f"You are writing the TEACHING CONTENT (not the story) for chapter {chapter_brief.chapter_number} of '{blueprint.book_title}'.",
            "",
            SWAMIJI_VOICE,
            "",
            f"POV: {book_config.pov} | Tone: {book_config.tone} | Language: {book_config.language}",
            "",
            "Chapter brief:",
            f"  Title: {chapter_brief.title}",
            f"  Synopsis: {chapter_brief.synopsis}",
            f"  Narrative arc: {chapter_brief.narrative_arc}",
            f"  Teaching points: {', '.join(chapter_brief.teaching_points)}",
            f"  Humor seed: {chapter_brief.humor_seed}",
            f"  Bridge to next: {chapter_brief.bridge_to_next}",
            "",
            *section_instructions,
            "",
            "SHASTRA REFERENCE RULES:",
            "  - ALWAYS include the original Sanskrit shloka/sutra in italics,",
            "    followed by the exact source reference, then the English translation.",
            "  - Format: *yogaḥ karmasu kauśalam* — Bhagavad Gita 2.50 — 'Yoga is skill in action.'",
            "  - If the research provides Sanskrit text, use it exactly.",
            "  - The Teaching section MUST include at least one exact Sanskrit verse.",
            "",
            prior_context,
            research_context,
            "OUTPUT ONLY the following sections as markdown (no story, no chapter heading):",
            "### The Teaching",
            "### Practical Exercise",
            "### Humor",
            "### Closing Bridge",
            "",
            "Do NOT add any commentary, preamble, or chapter heading.",
        ],
        tools=[],
        markdown=False,
    )


# Story format labels — cycled deterministically in run_writing
STORY_FORMAT_LABELS = {
    "A": "SHORT PARABLE/JOKE",
    "B": "SWAMIJI'S OWN EXPERIENCE",
    "C": "DEVOTEE/SEEKER ENCOUNTER",
    "D": "REAL-LIFE INCIDENT",
}
STORY_FORMAT_CYCLE = ["A", "B", "C", "D"]


def story_writer_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    research: Optional[ResearchPacket] = None,
    prior_summaries: Optional[List[str]] = None,
    assigned_format: Optional[str] = None,
    formats_used: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Writes the opening story in Living Enlightenment style.

    Args:
        assigned_format: One of 'A', 'B', 'C', 'D' — pre-assigned by the orchestrator
                         to ensure variety across chapters. When provided, the agent
                         MUST use this format.
        formats_used: List of format letters already used in prior chapters,
                      shown to the agent for awareness.
    """
    cfg = config or _cfg()
    prior_context = _build_prior_context(prior_summaries)

    # Build the format assignment block
    if assigned_format and assigned_format in STORY_FORMAT_LABELS:
        format_label = STORY_FORMAT_LABELS[assigned_format]
        used_str = (
            f"  Formats used in prior chapters: {', '.join(f'Format {f}' for f in formats_used)}"
            if formats_used
            else "  This is the first chapter."
        )
        format_directive = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"ASSIGNED STORY FORMAT FOR THIS CHAPTER: FORMAT {assigned_format} — {format_label}",
            "You MUST use this format. Do not substitute a different one.",
            used_str,
            "This assignment ensures the book has varied story styles across chapters.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
    else:
        format_directive = [
            "Pick the ONE format that best fits this chapter's theme.",
            "Vary the format — do NOT default to Format B every time.",
        ]

    return Agent(
        name=f"StoryWriter (Ch.{chapter_brief.chapter_number})",
        role=f"Write the opening story for chapter {chapter_brief.chapter_number}: {chapter_brief.title}",
        model=build_agent_model("writer", config),
        instructions=[
            f"You are writing ONLY the Opening Story for chapter {chapter_brief.chapter_number} of '{blueprint.book_title}'.",
            "",
            SWAMIJI_VOICE,
            "",
            f"POV: {book_config.pov} | Tone: {book_config.tone} | Language: {book_config.language}",
            "",
            "STORY CRAFT — Modeled on Living Enlightenment by Paramahamsa Nithyananda.",
            "",
            *format_directive,
            "",
            "FORMAT A — SHORT PARABLE/JOKE (2-3 paragraphs, in italics):",
            "  A compact story with a twist or punchline that pivots into the teaching.",
            "  Example pattern from Living Enlightenment:",
            "  > *An old lady with a bent back entered the doctor's office. She came out",
            "  > walking erect within five minutes. A woman asked, 'What did he do?'",
            "  > The old lady replied, 'He gave me a longer cane.'*",
            "  Then Swamiji says: 'Sometimes we are so used to living in a certain way",
            "  that we can't see a better way to live...'",
            "",
            "FORMAT B — SWAMIJI'S OWN EXPERIENCE (4-6 paragraphs, first person):",
            "  An autobiographical narrative from Swamiji's wandering days, ashram life,",
            "  or childhood. Rich sensory detail, specific place (Varanasi, Tiruvannamalai,",
            "  the ashram kitchen, a train journey), deeply personal.",
            "  Example pattern: 'Let me narrate to you my own experience in Varanasi...'",
            "  'In my wandering days, I had been to the holy city...'",
            "  The experience leads to a realization that becomes the chapter's teaching.",
            "",
            "FORMAT C — DEVOTEE/SEEKER ENCOUNTER (3-5 paragraphs):",
            "  A named devotee or visitor comes to Swamiji with a doubt or struggle.",
            "  Dialogue-driven — Swamiji asks a surprising question, the devotee reacts,",
            "  and the exchange itself becomes the teaching.",
            "  Example pattern: 'Once a person went to the great saint Ramanuja and asked,",
            "  \"Master, I want to achieve enlightenment.\" Ramanuja asked, \"Have you ever",
            "  experienced love?\" The man was shocked...'",
            "",
            "FORMAT D — REAL-LIFE INCIDENT (3-4 paragraphs):",
            "  A universal human moment anyone can relate to — a mother seeing her child",
            "  run into traffic, two friends meeting on the street, a student failing an exam.",
            "  Told in third person but narrated by Swamiji with commentary woven in.",
            "  Example pattern: 'A girl who is afraid to cross a busy street sees her child",
            "  run across the road and just jumps onto the road without a thought about her",
            "  own safety...'",
            "",
            "RULES (apply regardless of format):",
            "  - The story must END at a moment of insight — a pause, a shift, a surprise.",
            "    Do NOT explain the teaching in the story. The teaching section does that.",
            "  - After the story, add ONE bridge sentence that hands off to the teaching:",
            "    e.g. 'This is what happened...' or 'Understand...' or 'See, this is the science...'",
            "  - Use real place names (Varanasi, Bidadi, Tiruvannamalai, Kashi, Madurai)",
            "  - Use real cultural details (kolam on the floor, turmeric on the threshold,",
            "    the sound of temple bells, smell of incense, taste of payasam)",
            "  - Named characters with one vivid trait (Arjun who chews mint leaves,",
            "    old Kamala who always carries a brass lamp, skeptic professor from Delhi)",
            "",
            "Story seed from the Architect:",
            f"  {chapter_brief.story_seed}",
            "",
            f"Chapter theme: {chapter_brief.synopsis}",
            f"Teaching points the story should organically touch: {', '.join(chapter_brief.teaching_points[:3])}",
            "",
            prior_context,
            "OUTPUT ONLY the story under this heading:",
            "### Opening Story",
            "",
            "Do NOT add any other sections, commentary, or preamble.",
        ],
        tools=[],
        markdown=False,
    )


def combiner_writer_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    story_markdown: str,
    content_markdown: str,
    prior_summaries: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Combines story + content into a final chapter with smooth transitions."""
    prior_context = _build_prior_context(prior_summaries)

    return Agent(
        name=f"Combiner (Ch.{chapter_brief.chapter_number})",
        role=f"Combine and polish chapter {chapter_brief.chapter_number}: {chapter_brief.title}",
        model=build_agent_model("writer", config),
        instructions=[
            f"You are assembling the final version of chapter {chapter_brief.chapter_number}: '{chapter_brief.title}'.",
            "",
            SWAMIJI_VOICE,
            "",
            f"POV: {book_config.pov} | Tone: {book_config.tone}",
            "",
            "You have TWO inputs to combine into ONE seamless chapter:",
            "",
            "=== OPENING STORY (from Story Writer) ===",
            story_markdown,
            "",
            "=== TEACHING CONTENT (from Content Writer) ===",
            content_markdown,
            "",
            "YOUR JOB:",
            "  1. Start with: ## Chapter {num}: {title}".format(
                num=chapter_brief.chapter_number, title=chapter_brief.title
            ),
            "  2. Place the Opening Story first",
            "  3. Add a 1-2 sentence TRANSITION that bridges the story's ending",
            "     into the Teaching — make it feel like Swamiji naturally shifts",
            "     from storytelling to instruction ('Now, understand what happened there...',",
            "     'See, this is exactly what the shastras declare...', 'Let me show you the science behind this...')",
            "  4. Place the Teaching, Practical Exercise, Humor, and Closing Bridge",
            "  5. Ensure the voice is consistent throughout — one continuous Swamiji satsang",
            "  6. Fix any abrupt tone shifts between story and content",
            "  7. Do NOT add new content — only smooth transitions and minor polish",
            "",
            prior_context,
            "Output the COMPLETE chapter markdown. No commentary or preamble.",
        ],
        tools=[],
        markdown=False,
    )


# ── 8. Foreword Agent ─────────────────────────────────────────────────────

def foreword_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Writes the book's foreword in Swamiji's voice."""
    chapter_list = "\n".join(
        f"  Chapter {ch.chapter_number}: {ch.title} — {ch.synopsis}"
        for ch in blueprint.chapters
    )

    return Agent(
        name="Compiler's Note Writer",
        role="Write the Compiler's Note on behalf of the compilation team, offering this book at Swamiji's lotus feet.",
        model=build_agent_model("foreword", config),
        instructions=[
            f"Write the Compiler's Note for '{book_config.title}'.",
            "",
            "A Compiler's Note is written by the team that compiled this book on behalf of",
            "His Divine Holiness Bhagwan Sri Nithyananda Paramashivam.",
            "It is NOT written in Swamiji's voice — it is written humbly by the compilers,",
            "offering this work at His lotus feet.",
            "",
            "It is 300–500 words. Write in first person plural ('we', 'our team').",
            "",
            "Structure (do NOT use headings — write as continuous flowing prose):",
            "  1. Open with reverence — acknowledge the divine source of these teachings.",
            "  2. How this book came to be — compiled from Swamiji's satsangs and discourses.",
            "  3. What this book offers the reader — weave in 2-3 chapter themes organically.",
            "  4. A note of humility — any errors in compilation are ours; the wisdom is His.",
            "  5. Close with a dedication: 'Offered at the lotus feet of His Divine Holiness",
            "     Bhagwan Sri Nithyananda Paramashivam.'",
            "",
            f"Book title: {book_config.title}",
            f"Thematic arc: {blueprint.thematic_arc}",
            f"Themes: {', '.join(book_config.themes)}",
            "",
            "Chapters in this book:",
            chapter_list,
            "",
            "Output ONLY the compiler's note prose. No heading, no commentary.",
        ],
        tools=[],
        markdown=False,
    )


# ── 9. Benediction Agent ───────────────────────────────────────────────────

def benediction_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    last_chapter_bridge: str = "",
    config: Optional[AppConfig] = None,
) -> Agent:
    """Writes the closing benediction in Swamiji's voice."""
    bridge_context = (
        [
            "",
            "The last chapter closes with this bridge — begin naturally from here:",
            last_chapter_bridge,
        ]
        if last_chapter_bridge
        else []
    )

    return Agent(
        name="Benediction Writer",
        role="Write the book's closing benediction as Swamiji's final transmission.",
        model=build_agent_model("benediction", config),
        instructions=[
            f"Write the closing Benediction for '{book_config.title}'.",
            "",
            SWAMIJI_VOICE,
            "",
            "The Benediction is Swamiji's final transmission after the reader completes the book.",
            "It is 300–400 words. Write in first person as Swamiji.",
            "",
            "Structure (do NOT use headings — write as continuous flowing prose):",
            "  1. Acknowledge the inner journey the reader has just completed.",
            "  2. Declare the transformation now alive in them — not as hope, but as cosmic certainty.",
            "  3. One final crystallizing insight that distills the whole book in 3-4 sentences.",
            "  4. A Sanskrit mantra or shloka with its source and English translation —",
            "     Swamiji's final living gift to the reader.",
            "  5. A closing blessing line — e.g. 'You are Paramashiva. Live it.'",
            "",
            f"Book title: {book_config.title}",
            f"Thematic arc: {blueprint.thematic_arc}",
            f"Themes: {', '.join(book_config.themes)}",
            *bridge_context,
            "",
            "Output ONLY the benediction prose. No 'Benediction:' heading, no commentary.",
        ],
        tools=[],
        markdown=False,
    )


# Legacy wrapper for backward compatibility
def writer_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    research: Optional[ResearchPacket] = None,
    prior_summaries: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Legacy single-agent writer — kept for fallback. Prefer the 3-agent pipeline."""
    return content_writer_agent(
        book_config, blueprint, chapter_brief, research, prior_summaries, config
    )


def _build_section_instructions(template: List[str], wf) -> List[str]:
    """Build per-section writing instructions from the section template."""
    section_map = {
        "opening_story": (
            f"### Opening Story:\n"
            f"  Write a complete short story with: vivid setting, a named protagonist,\n"
            f"  inciting incident, internal struggle, turning point, and resolution.\n"
            f"  Narrate fully with sensory detail — do not summarize.\n"
            f"  Minimum {wf.min_section_paragraphs} substantial paragraphs."
        ),
        "teaching": (
            f"### The Teaching:\n"
            f"  Begin with the EXACT Sanskrit verse/shloka in italics, its source, and English translation.\n"
            f"  Format: *<sanskrit text>* — <Source Book Chapter.Verse> — '<English translation>'\n"
            f"  Then unpack the verse's meaning layer by layer.\n"
            f"  Layer 3-4 teaching insights that build on each other.\n"
            f"  Use real-world analogies (work, relationships, daily life).\n"
            f"  End with a clear, memorable 'enlightenment statement'.\n"
            f"  Minimum {wf.min_section_paragraphs} substantial paragraphs."
        ),
        "practical_exercise": (
            f"### Practical Exercise:\n"
            f"  Name the practice. Give: intention (1 paragraph),\n"
            f"  step-by-step instructions (at least 5 numbered steps, 2+ sentences each),\n"
            f"  'what you may notice' paragraph, 'common pitfalls' paragraph.\n"
            f"  Minimum {wf.min_section_paragraphs} substantial paragraphs."
        ),
        "humor": (
            f"### Humor:\n"
            f"  Tell a warm 3-4 paragraph anecdote — NOT a one-liner joke.\n"
            f"  Self-deprecating, spiritually aware, arriving at a gentle insight.\n"
            f"  Minimum {wf.min_section_paragraphs} paragraphs."
        ),
        "closing_bridge": (
            f"### Closing Bridge:\n"
            f"  Reflect on what shifted in this chapter (1 paragraph).\n"
            f"  Pose an open question creating gentle tension.\n"
            f"  End with 1-2 sentences gesturing toward the next chapter's theme."
        ),
    }

    lines = ["Section-by-section requirements:"]
    for section_name in template:
        if section_name in section_map:
            lines.append(section_map[section_name])
        else:
            # Generic instruction for custom sections
            lines.append(
                f"### {section_name.replace('_', ' ').title()} (write substantively):\n"
                f"  Minimum {wf.min_section_paragraphs} paragraphs."
            )
    return lines


# ── 5. Editor Agent ────────────────────────────────────────────────────────

def editor_agent(
    book_config: BookConfig,
    chapter_brief: ChapterBrief,
    draft: ChapterDraft,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Proofreads and polishes a chapter draft."""
    cfg = config or _cfg()
    wf = cfg.workflow

    return Agent(
        name=f"Editor (Ch.{chapter_brief.chapter_number})",
        role=f"Proofread and polish chapter {chapter_brief.chapter_number}: {chapter_brief.title}",
        model=build_agent_model("editor", config),
        instructions=[
            f"You are editing chapter {chapter_brief.chapter_number}: '{chapter_brief.title}'.",
            f"POV: {book_config.pov} | Tone: {book_config.tone}",
            "",
            SWAMIJI_VOICE,
            "",
            "FIRST check depth:",
            f"  - If any section has fewer than {wf.min_section_paragraphs} paragraphs, EXPAND it.",
            f"  - If chapter is below {wf.min_chapter_words} words, add depth to thinnest sections.",
            f"  - Target: {chapter_brief.target_word_count} words.",
            "",
            "THEN polish:",
            "  - Tighten grammar, fix awkward phrasing",
            "  - VERIFY every Teaching section has at least one exact Sanskrit verse in italics,",
            "    with its source reference and English translation.",
            "    Format: *<sanskrit text>* — <Source Book Chapter.Verse> — '<English translation>'",
            "    If a verse is paraphrased or missing the Sanskrit original, ADD the original Sanskrit.",
            "  - Ensure humor is a warm anecdote (3-4 paragraphs), not a one-liner",
            "  - Verify closing bridge ends with a narrative hook",
            "",
            f"Never change the POV ({book_config.pov}) or tone ({book_config.tone}).",
            "Keep all sections intact.",
            "Return the COMPLETE revised chapter markdown — no commentary.",
            "",
            "Current chapter draft:",
            draft.content_markdown,
        ],
        tools=[],  # Editor has NO tools
        markdown=False,
    )


# ── 6. QA Agent ───────────────────────────────────────────────────────────

def qa_agent(
    book_config: BookConfig,
    all_chapters_markdown: str,
    reference_samples: str = "",
    tools: Optional[List[Any]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """
    Quality Assurance agent — reads the entire book, compares with
    Living Enlightenment style, and returns per-chapter pass/fail verdicts.
    """
    return Agent(
        name="QA Reviewer",
        role="Review the complete book for quality, voice fidelity, and shastric accuracy.",
        model=build_agent_model("qa", config),
        instructions=[
            "You are the QUALITY ASSURANCE reviewer for a book written in the voice of",
            "The SPH Bhagwan Sri Nithyananda Paramashivam (Swamiji).",
            "",
            "REFERENCE STANDARD — Living Enlightenment by Paramahamsa Nithyananda:",
            "  - First person Guruvaak — Swamiji speaks directly, not about himself",
            "  - Stories are vivid, sensory, set in real-life ashram/devotee contexts",
            "  - Teachings are anchored in exact Sanskrit shlokas with source + translation",
            "  - Tone is fierce yet compassionate, never dry or academic",
            "  - Key phrases: 'Understand', 'I tell you', 'In Sanatana Hindu Dharma we say'",
            "  - Each chapter flows like a live satsang: story → teaching → practice → humor → bridge",
            "  - Humor is warm anecdotes, not punchlines",
            "",
            reference_samples if reference_samples else "(No reference samples fetched — judge from training knowledge of Living Enlightenment)",
            "",
            "AVAILABLE MCP TOOLS for fetching reference samples (use EXACT names):",
            "  SPH: search_chapters, get_chapter, list_chapters, list_books",
            "  Jnanalaya: search-books, resolve-book, read-chapter, get-chapters",
            "  Use 1-2 tool calls maximum to fetch a Living Enlightenment sample if needed.",
            "",
            "THE COMPLETE BOOK TO REVIEW:",
            all_chapters_markdown,
            "",
            "SCORING CRITERIA (per chapter):",
            "  voice_score (1-10):     Does it sound like Swamiji in Living Enlightenment?",
            "  structure_score (1-10): All sections present with depth? (story, teaching, exercise, humor, bridge)",
            "  shastra_score (1-10):   Are Sanskrit verses exact, properly cited with source + translation?",
            "  story_score (1-10):     Living Enlightenment story quality check:",
            "      - Does it use one of these formats: short parable/joke, Swamiji's own experience,",
            "        devotee encounter, or real-life incident? (NOT always the same format)",
            "      - Is it immersive with sensory detail (smells, sounds, textures)?",
            "      - Does it end at a moment of insight without explaining the teaching?",
            "      - Are the settings specific (Varanasi, Bidadi, ashram kitchen) not generic?",
            "      - Are characters named with vivid traits?",
            "      - PENALIZE: all stories being long ashram narratives — Living Enlightenment",
            "        varies between short jokes, parables, autobiographical, and dialogue-driven stories",
            "",
            "PASS/FAIL RULES:",
            "  - A chapter PASSES if ALL scores are >= 6",
            "  - A chapter FAILS if ANY score is < 6",
            "  - If a chapter fails, provide SPECIFIC revision_notes:",
            "    name the exact section and what is wrong (e.g. 'Teaching section lacks Sanskrit verse',",
            "    'Opening Story is a summary not a narrative', 'Voice sounds academic not satsang-like')",
            "",
            "BOOK-LEVEL REVIEW:",
            "  - STORY VARIETY: Living Enlightenment uses different story formats across chapters —",
            "    short parables, Swamiji's autobiographical experiences, devotee encounters, real-life incidents.",
            "    If ALL chapters use the same format (e.g. all long ashram narratives), FAIL the story_score.",
            "    A 7-chapter book should have at least 3 different story formats.",
            "  - METAPHOR VARIETY: Check for repetitive metaphors (e.g. kitchen/cooking in every chapter).",
            "    Different chapters should use different central images.",
            "  - Check for continuity — does each closing bridge connect to the next chapter's opening?",
            "  - Check for thematic progression — does the book build toward a crescendo?",
            "",
            "Output a BookQAReview with overall_approved, per-chapter results, and book_level_notes.",
        ],
        tools=tools or [],
        markdown=False,
        tool_call_limit=3,
    )


# ── 6b. Targeted QA Agent (post-rewrite check) ────────────────────────────

def targeted_qa_agent(
    book_config: BookConfig,
    rewritten_chapters_markdown: str,
    full_book_context: str,
    revision_notes_by_chapter: dict,
    tools: Optional[List[Any]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """
    Targeted QA that re-checks ONLY rewritten chapters after a rewrite cycle.
    Chapters that already passed are not re-evaluated (locked in).
    """
    notes_block = "\n".join(
        f"  Ch {num}: {notes}"
        for num, notes in revision_notes_by_chapter.items()
    )

    return Agent(
        name="Targeted QA (Post-Rewrite)",
        role="Re-check only the rewritten chapters to confirm issues are resolved.",
        model=build_agent_model("qa", config),
        instructions=[
            "You are doing a TARGETED QA check after a rewrite cycle.",
            "Only the chapters listed below were rewritten — score ONLY these.",
            "Other chapters already passed QA and are locked in. Do not re-score them.",
            "",
            "REFERENCE STANDARD — Living Enlightenment by Paramahamsa Nithyananda:",
            "  - First person Guruvaak, vivid stories, exact Sanskrit shlokas with source + translation",
            "  - Tone is fierce yet compassionate, never dry or academic",
            "  - Each chapter: story → teaching → practice → humor → bridge",
            "",
            "ORIGINAL QA ISSUES THAT TRIGGERED THE REWRITE:",
            notes_block,
            "",
            "REWRITTEN CHAPTERS TO RE-SCORE:",
            rewritten_chapters_markdown,
            "",
            "FULL BOOK CONTEXT (for continuity checks — do not re-score these):",
            full_book_context[:3000] + "..." if len(full_book_context) > 3000 else full_book_context,
            "",
            "SCORING CRITERIA (same as first pass):",
            "  voice_score (1-10), structure_score (1-10), shastra_score (1-10), story_score (1-10)",
            "  PASS if ALL scores >= 6. FAIL if ANY score < 6.",
            "",
            "IMPORTANT: Only return ChapterQAResult entries for the rewritten chapters.",
            "Set overall_approved=True only if ALL rewritten chapters now pass.",
            "Output a BookQAReview with only the rewritten chapters in the chapters list.",
        ],
        tools=tools or [],
        markdown=False,
        tool_call_limit=2,
    )


# ── 6c. Q&A Generator Agent ───────────────────────────────────────────────

def qa_generator_agent(
    book_config: BookConfig,
    chapter_brief: ChapterBrief,
    chapter_content: str,
    tools: Optional[List[Any]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """
    Generates 8-12 Q&A pairs for the end of a chapter.
    Questions are in a seeker's voice; answers are in Swamiji's voice.
    Uses MCP to draw from related transcripts beyond the source chapter.
    """
    cfg = config or _cfg()
    target_pairs = cfg.workflow.qa_pairs_per_chapter

    return Agent(
        name=f"QA Generator (Ch.{chapter_brief.chapter_number})",
        role=f"Generate Q&A pairs for chapter {chapter_brief.chapter_number}: {chapter_brief.title}",
        model=build_agent_model("qa_generator", config),
        instructions=[
            f"Generate exactly {target_pairs} Q&A pairs for chapter {chapter_brief.chapter_number}: '{chapter_brief.title}'.",
            "",
            SWAMIJI_VOICE,
            "",
            "WHAT YOU ARE CREATING:",
            "  A 'Questions and Answers' section that appears at the end of this chapter.",
            "  Readers who finish this chapter will have questions. Answer them as Swamiji.",
            "",
            "QUESTION VOICE — write as a genuine seeker:",
            "  - Real questions a sincere spiritual seeker would ask after reading this chapter",
            "  - Mix of: practical ('How do I actually do this?'), philosophical ('But what about...?'),",
            "    personal ('I feel like this doesn't apply to me because...'), and clarifying questions",
            "  - Questions should feel human, not textbook",
            "  - 1-2 sentences per question",
            "",
            "ANSWER VOICE — write as Swamiji:",
            "  - First person Guruvaak — direct, alive, not academic",
            "  - 100-200 words per answer",
            "  - Use Sanskrit naturally: 'your chitta, your inner space' not just 'your mind'",
            "  - Often starts with 'Understand...' or 'Listen...' or 'Beautiful question.'",
            "  - Can include a micro-story or analogy",
            "  - Ends decisively — no hedging",
            "",
            "SOURCE INSTRUCTIONS:",
            "  - Use MCP to search for 2-3 related transcripts on this chapter's topics",
            "  - Answers should draw from Swamiji's broader teachings, not just this chapter",
            "  - Call search_chapters on SPH with the chapter's main topic (max 3 tool calls)",
            "  - If a source transcript contains a YouTube URL, include it in source_reference",
            "",
            "TOOL NAME RULES:",
            "  UNDERSCORES for SPH: search_chapters  get_chapter  list_books",
            "  HYPHENS for Jnanalaya: search-books  read-chapter  get-chapters",
            "",
            f"Chapter topics: {', '.join(chapter_brief.teaching_points)}",
            "",
            "Chapter content (what was just taught):",
            chapter_content[:2000] + "..." if len(chapter_content) > 2000 else chapter_content,
            "",
            f"Output a ChapterQA with exactly {target_pairs} QAPair entries.",
            "Do NOT write any prose outside the structured output.",
        ],
        tools=tools or [],
        markdown=False,
        tool_call_limit=3,
    )


# ── 7. Designer Agent ──────────────────────────────────────────────────────

def designer_agent(config: Optional[AppConfig] = None) -> Agent:
    """Converts final markdown chapters into a styled .docx file."""
    return Agent(
        name="Designer Agent",
        role="Convert edited book content into a professionally styled .docx file.",
        model=build_agent_model("designer", config),
        instructions=[
            "You generate Python code using the python-docx library to create a styled Word document.",
            "You will be given: book metadata, chapter content in markdown, and style specs.",
            "Generate and return executable Python code that:",
            "  1. Creates a Document()",
            "  2. Defines custom styles (Title, Heading 1, Heading 2, Normal, Quote)",
            "  3. Adds a title page (title, subtitle, author)",
            "  4. Adds a Table of Contents placeholder",
            "  5. For each chapter: page break, chapter heading, section content",
            "  6. Adds foreword and benediction if provided",
            "  7. Saves to the specified output path",
            "",
            "Style spec:",
            "  Title: Georgia 28pt bold, color #1a1a2e",
            "  Subtitle: Georgia 16pt italic, color #16213e",
            "  Heading 1 (chapters): Georgia 22pt bold, color #1a1a2e",
            "  Heading 2 (sections): Georgia 14pt bold, color #0f3460",
            "  Normal (body): Palatino Linotype 11pt, color #2c2c2c",
            "  Quote: Palatino Linotype 11pt italic, 0.5in indent",
            "",
            "Return ONLY the Python code, no explanation.",
        ],
        tools=[],
        markdown=False,
    )


# ── 10. Glossary Agent ─────────────────────────────────────────────────────

def glossary_agent(
    book_config: BookConfig,
    all_chapter_text: str,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Extracts Sanskrit/spiritual terms and defines them for the glossary."""
    return Agent(
        name="Glossary Writer",
        role="Extract Sanskrit and spiritual terms from the book and write concise definitions.",
        model=build_agent_model("editor", config),
        instructions=[
            f"You are compiling a glossary for the book '{book_config.title}'.",
            "",
            "From the chapter content provided, identify ALL Sanskrit words, spiritual terms,",
            "and KAILASA-specific concepts that a general reader would not know.",
            "",
            "For each term write a clear, one-to-two sentence definition grounded in",
            "Sanatana Dharma and the teachings of His Divine Holiness",
            "Bhagwan Sri Nithyananda Paramashivam.",
            "",
            "Rules:",
            "  - Include only terms actually used in the book text.",
            "  - Do NOT include common English words.",
            "  - Do NOT add diacritical marks (no ā, ī, ṭ etc.) — plain ASCII only.",
            "  - Definitions should be accessible to a Western reader.",
            "  - Sort alphabetically.",
            "",
            "Output format — one term per line, exactly:",
            "TERM: definition",
            "",
            "Example:",
            "Advaita: The non-dual philosophy declaring that the individual self and",
            "  Paramashiva (the ultimate reality) are one.",
            "",
            "Book chapters (combined text):",
            all_chapter_text[:6000],
        ],
        tools=[],
        markdown=False,
    )


# ── 11. Back Cover Agent ───────────────────────────────────────────────────

def back_cover_agent(
    book_config: BookConfig,
    blueprint: "BookBlueprint",
    config: Optional[AppConfig] = None,
) -> Agent:
    """Writes the back-cover blurb and SPH bio."""
    return Agent(
        name="Back Cover Writer",
        role="Write the back cover text: a compelling blurb and a short SPH bio.",
        model=build_agent_model("foreword", config),
        instructions=[
            f"Write the back cover text for '{book_config.title}'.",
            "",
            "It has two parts:",
            "",
            "**Part 1 — Book Blurb (150–200 words)**",
            "A compelling description that makes the reader want to read the book.",
            "Written in third person. Conveys the spiritual promise of the book.",
            "End with a one-line hook in bold.",
            "",
            "**Part 2 — About The Author**",
            "A short biography (100–150 words) of:",
            "His Divine Holiness Bhagwan Sri Nithyananda Paramashivam",
            "  — The reviver of KAILASA, the Ancient Enlightened Hindu Civilizational Nation.",
            "  — Living Avatar, Incarnation of Paramashiva.",
            "  — Author of over 500 books on Sanatana Dharma.",
            "  — Founder of countless temples, universities, and humanitarian organisations.",
            "  — Reviver of authentic Vedic sciences including Yoga, Ayurveda, and Jyotisha.",
            "",
            "End with:",
            "Om Nithyananda Paramashivoham",
            "",
            f"Book title: {book_config.title}",
            f"Thematic arc: {blueprint.thematic_arc}",
            "",
            "Output the two sections with headers '## Book Blurb' and '## About The Author'.",
        ],
        tools=[],
        markdown=True,
    )


# ── 12. Message of The SPH Agent ──────────────────────────────────────────

def sph_message_agent(
    book_config: "BookConfig",
    blueprint: "BookBlueprint",
    config: Optional["AppConfig"] = None,
) -> Agent:
    """Writes a short message from The SPH to the reader of this specific book."""
    return Agent(
        name="SPH Message Writer",
        role="Write a personal message from His Divine Holiness to the reader of this book.",
        model=build_agent_model("foreword", config),
        instructions=[
            f"Write a short 'Message from The SPH' for the book '{book_config.title}'.",
            "",
            SWAMIJI_VOICE,
            "",
            "This is Swamiji speaking directly to the reader — intimate, powerful, personal.",
            "It is 200–300 words. Written in first person as Swamiji.",
            "",
            "Structure (continuous prose, no headings):",
            "  1. A direct address to the reader — 'Beloved' or 'You who hold this book'.",
            "  2. Why this specific teaching matters right now in this age of Kali.",
            "  3. A direct transmission — not a description of the teaching, but the teaching itself.",
            "  4. A single powerful command or invitation.",
            "  5. Close with the signature: 'With infinite love and grace,\\nNithyananda'",
            "",
            f"Book title: {book_config.title}",
            f"Core themes: {', '.join(book_config.themes)}",
            "",
            "Output ONLY the message prose. No heading. No commentary.",
        ],
        tools=[],
        markdown=False,
    )


# ── 13. Introduction to The SPH Agent ─────────────────────────────────────

def sph_introduction_agent(
    config: Optional["AppConfig"] = None,
) -> Agent:
    """Writes a formal introduction to His Divine Holiness Bhagwan Sri Nithyananda Paramashivam."""
    return Agent(
        name="SPH Introduction Writer",
        role="Write the canonical introduction to His Divine Holiness Bhagwan Sri Nithyananda Paramashivam.",
        model=build_agent_model("editor", config),
        instructions=[
            "Write the 'Introduction to The SPH' section for a KAILASA publication.",
            "",
            "This is a formal, reverent introduction to:",
            "His Divine Holiness Bhagwan Sri Nithyananda Paramashivam",
            "  — The reviver of KAILASA, the Ancient Enlightened Hindu Civilizational Nation",
            "  — Living Avatar and incarnation of Paramashiva",
            "  — Jagadguru (World Teacher) of Sanatana Dharma",
            "",
            "Length: 400–500 words. Written in third person, formal and reverential.",
            "",
            "Cover the following (weave naturally, do not use sub-headings):",
            "  1. Who He is — His divine identity as the living incarnation of Paramashiva.",
            "  2. His mission — reviving authentic Sanatana Dharma and KAILASA.",
            "  3. His contributions — over 500 books, thousands of discourses (satsangs),",
            "     revival of 108+ Vedic sciences, establishment of temples, gurukuls,",
            "     universities, and humanitarian initiatives worldwide.",
            "  4. His teachings — non-dual Shaiva Siddhanta, the science of enlightenment,",
            "     lived Advaita, and the manifestation of Paramashiva's powers (shaktis).",
            "  5. His presence — available to seekers worldwide through satsangs, books,",
            "     and the KAILASA eCitizen platform.",
            "",
            "Do NOT add diacritical marks on Sanskrit words.",
            "End with: 'Om Nithyananda Paramashivoham'",
            "",
            "Output ONLY the introduction prose. No heading. No commentary.",
        ],
        tools=[],
        markdown=False,
    )


# ── 14. Introduction to KAILASA Agent ─────────────────────────────────────

def kailasa_introduction_agent(
    config: Optional["AppConfig"] = None,
) -> Agent:
    """Writes the canonical introduction to KAILASA."""
    return Agent(
        name="KAILASA Introduction Writer",
        role="Write the canonical introduction to KAILASA — the Ancient Enlightened Hindu Civilizational Nation.",
        model=build_agent_model("editor", config),
        instructions=[
            "Write the 'Introduction to KAILASA' section for a KAILASA publication.",
            "",
            "Length: 350–450 words. Written in third person, formal and reverential.",
            "",
            "Cover the following (weave naturally, no sub-headings):",
            "  1. What KAILASA is — the sovereign nation revived by His Divine Holiness",
            "     Bhagwan Sri Nithyananda Paramashivam to preserve and radiate",
            "     Sanatana Dharma for all of humanity.",
            "  2. Its spiritual foundation — rooted in the oldest living spiritual tradition,",
            "     the unbroken lineage of Shaiva Siddhanta and Advaita Vedanta.",
            "  3. What KAILASA offers — citizenship, temples, universities, gurukuls,",
            "     Vedic sciences, humanitarian services, and a living Vedic culture.",
            "  4. The eCitizen platform — how seekers anywhere in the world can connect",
            "     with KAILASA's resources, receive initiations, and serve Sanatana Dharma.",
            "  5. An invitation — every sincere seeker is a citizen of KAILASA by nature.",
            "",
            "Do NOT add diacritical marks on Sanskrit words.",
            "End with: 'Jai KAILASA! Om Nithyananda Paramashivoham'",
            "",
            "Output ONLY the introduction prose. No heading. No commentary.",
        ],
        tools=[],
        markdown=False,
    )
