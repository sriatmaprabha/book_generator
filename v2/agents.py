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
        "You are a book architect. Design a detailed chapter-by-chapter blueprint.",
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
        "Section template for each chapter: " + " -> ".join(book_config.section_template),
        "",
        "For EACH chapter brief you MUST provide:",
        "  - title: a compelling chapter title",
        "  - synopsis: 2-3 sentences on what this chapter covers",
        "  - story_seed: AT LEAST 3 sentences — protagonist, setting, conflict, turning point",
        "  - narrative_arc: 3-5 sentences tracing the insight progression",
        "  - teaching_points: list of key points this chapter teaches",
        "  - verse_references: exact shastra references — include the original Sanskrit verse/shloka/sutra",
        "    along with its source (e.g. 'Bhagavad Gita 2.47', 'Patanjali Yoga Sutra 1.2', 'Vivekachudamani 20').",
        "    The Writer will translate these and weave them into the teaching.",
        "  - humor_seed: 2-3 sentence warm anecdote scenario (NOT a punchline)",
        "  - bridge_to_next: 2-3 sentences forming a narrative hook into the next chapter",
        f"  - target_word_count: default {book_config.words_per_chapter}, adjust for pivotal chapters",
        "",
        "Also provide:",
        "  - thematic_arc: how the reader transforms from chapter 1 to the last",
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
            "Output a ResearchPacket. Do NOT write prose.",
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


def story_writer_agent(
    book_config: BookConfig,
    blueprint: BookBlueprint,
    chapter_brief: ChapterBrief,
    research: Optional[ResearchPacket] = None,
    prior_summaries: Optional[List[str]] = None,
    config: Optional[AppConfig] = None,
) -> Agent:
    """Writes the opening story in Living Enlightenment style."""
    cfg = config or _cfg()
    wf = cfg.workflow
    prior_context = _build_prior_context(prior_summaries)

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
            "In Living Enlightenment, Swamiji uses MULTIPLE story formats.",
            "Pick the ONE format that best fits this chapter's theme:",
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
            "CRUCIAL RULES:",
            "  - Do NOT always use Format B. Vary across chapters. If prior chapters used",
            "    ashram stories, use a parable or devotee encounter this time.",
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
