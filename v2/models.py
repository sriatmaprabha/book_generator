"""
Pydantic data models for the book generation pipeline.

All voice/style fields are plain str — descriptions guide the user,
but nothing is hard-coded or constrained to an enum.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ── User Input ──────────────────────────────────────────────────────────────

class BookConfig(BaseModel):
    """Everything the user specifies before generation begins."""

    # Core
    title: str = Field(..., description="Working title of the book")
    subtitle: Optional[str] = Field(None, description="Optional subtitle")
    author: str = Field(
        "The SPH Bhagwan Sri Nithyananda Paramashivam",
        description="Author name for the cover page",
    )

    # Structure
    num_chapters: int = Field(..., ge=3, le=20, description="Number of chapters to generate")
    words_per_chapter: int = Field(
        2500, ge=1000, le=8000,
        description="Target word count per chapter",
    )
    chapter_titles: Optional[List[str]] = Field(
        None,
        description="Optional list of chapter titles — if omitted, the Architect generates them",
    )

    # Voice & Style (all str — descriptions are guidance, not constraints)
    pov: str = Field(
        "first person",
        description="Point of view: e.g. 'first person', 'second person', 'third person', 'omniscient narrator'",
    )
    tone: str = Field(
        "spiritual-conversational",
        description="Overall tone: e.g. 'academic', 'conversational', 'literary', 'satirical', 'spiritual-conversational'",
    )
    reading_level: str = Field(
        "intermediate",
        description="Target reading level: e.g. 'casual', 'intermediate', 'scholarly', 'young-adult'",
    )
    language: str = Field("English", description="Language the book should be written in")

    # Content
    synopsis: str = Field(
        ...,
        description="200-1000 word synopsis / premise — the big idea of the book",
    )
    themes: List[str] = Field(
        ..., min_length=1,
        description="Key themes the book should weave throughout, e.g. ['witnessing', 'awareness', 'surrender']",
    )
    target_audience: str = Field(
        ...,
        description="Who is this book for? e.g. 'Spiritual seekers aged 25-50'",
    )
    reference_sources: List[str] = Field(
        default_factory=list,
        description="MCP server URLs, file paths, or web links the agents should consult",
    )

    # Format
    section_template: List[str] = Field(
        default_factory=lambda: [
            "opening_story",
            "teaching",
            "practical_exercise",
            "humor",
            "closing_bridge",
        ],
        description="Ordered list of section names each chapter should contain",
    )
    include_foreword: bool = Field(True, description="Whether to include a foreword")
    include_benediction: bool = Field(True, description="Whether to include a closing benediction")
    include_toc: bool = Field(True, description="Whether to include a table of contents")


# ── Architect Output ────────────────────────────────────────────────────────

class ChapterBrief(BaseModel):
    """One chapter's blueprint — everything needed to research and write it."""

    chapter_number: int = Field(..., ge=1)
    title: str
    synopsis: str = Field(
        ...,
        description="2-3 sentence summary of what this chapter covers",
    )
    story_seed: str = Field(
        ...,
        description=(
            "At least 3 sentences: protagonist, setting, conflict, turning point. "
            "This seeds the opening story."
        ),
    )
    narrative_arc: str = Field(
        ...,
        description=(
            "3-5 sentences tracing how the insight unfolds across the chapter: "
            "opening confusion -> first insight -> deeper understanding -> practical realisation"
        ),
    )
    teaching_points: List[str] = Field(
        ..., min_length=1,
        description="Key teaching points this chapter must cover",
    )
    verse_references: List[str] = Field(
        default_factory=list,
        description="Specific verse/sutra/quote references to anchor the teaching",
    )
    humor_seed: str = Field(
        "",
        description=(
            "2-3 sentence warm anecdote/scenario — NOT a punchline. "
            "Think: a self-deprecating story a wise teacher might tell."
        ),
    )
    bridge_to_next: str = Field(
        "",
        description="2-3 sentences forming a narrative hook that closes this chapter and opens the next",
    )
    target_word_count: int = Field(
        2500, ge=1000, le=8000,
        description="Per-chapter word target (inherits from BookConfig.words_per_chapter unless overridden)",
    )

    # ── Book structure fields ──────────────────────────────────────────────
    chapter_type: str = Field(
        "main",
        description=(
            "Role of this chapter in the book structure. "
            "One of: 'preface' | 'introduction' | 'preliminary' | 'main' | 'conclusion'"
        ),
    )
    section_group: str = Field(
        "",
        description=(
            "The named section this chapter belongs to, e.g. 'Part I: The Ground of Being'. "
            "Chapters with the same section_group are rendered under one section divider page."
        ),
    )


class BookSectionGroup(BaseModel):
    """A named section grouping chapters — renders as a divider page in the .docx."""

    label: str = Field(
        ...,
        description="Section title shown on the divider page, e.g. 'Part I: The Ground of Being'",
    )
    chapter_numbers: List[int] = Field(
        ...,
        description="Ordered list of chapter numbers that belong to this section",
    )
    description: str = Field(
        "",
        description="1-2 sentences describing what this section covers — printed under the label",
    )


class BookBlueprint(BaseModel):
    """The complete book design — output of the Architect agent."""

    book_title: str
    thematic_arc: str = Field(
        ...,
        description="Book-level narrative arc: how the reader's understanding transforms from chapter 1 to N",
    )
    recurring_motifs: List[str] = Field(
        default_factory=list,
        description="Images, phrases, or ideas that recur across chapters for cohesion",
    )
    chapters: List[ChapterBrief]
    sections: List[BookSectionGroup] = Field(
        default_factory=list,
        description="Named section groups — each renders as a divider page before its first chapter",
    )
    voice_notes: str = Field(
        "",
        description="Guidance for the Writer on tone, speech patterns, humor policy, etc.",
    )


# ── Researcher Output ──────────────────────────────────────────────────────

class SourceLink(BaseModel):
    """A YouTube / video source link extracted from a research transcript."""

    title: str = Field(..., description="Title of the satsang or video")
    url: str = Field(..., description="Full YouTube URL (youtube.com/watch or youtu.be)")
    date: str = Field("", description="Date of the satsang/video if available, e.g. '14 Mar 2019'")
    chapter_number: int = Field(..., ge=1, description="Chapter that used this source")


class ResearchPacket(BaseModel):
    """Raw material gathered for a single chapter — fed to the Writer."""

    chapter_number: int = Field(..., ge=1)
    quotes: List[dict] = Field(
        default_factory=list,
        description='List of {"text": ..., "source": ...} quote objects',
    )
    key_facts: List[str] = Field(default_factory=list)
    anecdotes: List[str] = Field(default_factory=list)
    suggested_references: List[str] = Field(default_factory=list)
    source_links: List[SourceLink] = Field(
        default_factory=list,
        description="YouTube/video links extracted from MCP transcript responses",
    )


# ── Writer Intermediate Outputs ────────────────────────────────────────────

class StoryDraft(BaseModel):
    """Opening story written by the Story Writer agent."""
    chapter_number: int = Field(..., ge=1)
    story_markdown: str = Field(..., description="Opening Story section in markdown")
    word_count: int = Field(default=0, ge=0)


class ContentDraft(BaseModel):
    """Teaching content written by the Content Writer agent."""
    chapter_number: int = Field(..., ge=1)
    content_markdown: str = Field(
        ...,
        description="Teaching + Exercise + Humor + Bridge sections in markdown",
    )
    word_count: int = Field(default=0, ge=0)


# ── Writer Final Output ───────────────────────────────────────────────────

class ChapterDraft(BaseModel):
    """A complete chapter assembled by the Combiner agent."""

    chapter_number: int = Field(..., ge=1)
    title: str
    content_markdown: str = Field(..., description="Full chapter content in markdown")
    word_count: int = Field(..., ge=1)
    summary: str = Field(
        ...,
        description="2-3 sentence summary for rolling context passed to subsequent chapters",
    )


# ── Editor Output ──────────────────────────────────────────────────────────

class EditedChapter(BaseModel):
    """A polished chapter — output of the Editor agent."""

    chapter_number: int = Field(..., ge=1)
    title: str
    content_markdown: str
    final_word_count: int = Field(..., ge=1)
    changes_made: List[str] = Field(
        default_factory=list,
        description="Brief list of what was changed during editing",
    )


# ── Admin Review ────────────────────────────────────────────────────────────

class AdminReview(BaseModel):
    """Quality gate decision from the admin checkpoint."""

    approved: bool
    issues: List[str] = Field(default_factory=list)
    retry_target: str = Field(
        "none",
        description="Which agent should retry: 'architect', 'writer', 'editor', or 'none'",
    )
    revision_notes: str = ""


# ── QA Review ──────────────────────────────────────────────────────────────

class ChapterQAResult(BaseModel):
    """QA verdict for a single chapter."""
    chapter_number: int = Field(..., ge=1)
    passed: bool
    voice_score: int = Field(
        ..., ge=1, le=10,
        description="1-10: How well does this match Swamiji's voice in Living Enlightenment?",
    )
    structure_score: int = Field(
        ..., ge=1, le=10,
        description="1-10: Does it have all sections with proper depth?",
    )
    shastra_score: int = Field(
        ..., ge=1, le=10,
        description="1-10: Are Sanskrit verses present, exact, and properly cited?",
    )
    story_score: int = Field(
        ..., ge=1, le=10,
        description="1-10: Is the opening story immersive, sensory, Living-Enlightenment quality?",
    )
    issues: List[str] = Field(default_factory=list)
    revision_notes: str = Field(
        "",
        description="Specific instructions for rewriting — name exact sections and what to fix",
    )


class BookQAReview(BaseModel):
    """Full QA review across all chapters."""
    overall_approved: bool
    chapters: List[ChapterQAResult]
    book_level_notes: str = Field(
        "",
        description="Cross-chapter issues: continuity gaps, repetitive motifs, tone drift",
    )


# ── Compiled Metadata ──────────────────────────────────────────────────────

class QAPair(BaseModel):
    """A single question-and-answer pair for the end-of-chapter Q&A section."""

    question: str = Field(
        ...,
        description="A seeker's genuine question arising from this chapter's teaching (1-2 sentences)",
    )
    answer: str = Field(
        ...,
        description="Swamiji's answer in first-person Guruvaak voice (100-200 words)",
    )
    source_reference: str = Field(
        "",
        description="Title/date of the transcript or book this answer draws from",
    )


class ChapterQA(BaseModel):
    """All Q&A pairs for one chapter — appended after the chapter content."""

    chapter_number: int = Field(..., ge=1)
    chapter_title: str
    qa_pairs: List[QAPair] = Field(
        ..., min_length=1,
        description="8-12 Q&A pairs covering the chapter's key teachings",
    )


class CompiledBookMetadata(BaseModel):
    """Final book metadata assembled after all chapters are edited."""

    title: str
    subtitle: Optional[str] = None
    author: str
    synopsis: str
    foreword: str = ""
    benediction: str = ""
    source_notes: List[str] = Field(default_factory=list)
    all_source_links: List[SourceLink] = Field(
        default_factory=list,
        description="All YouTube source links across all chapters — exported for QR code generation",
    )
    chapter_count: int = Field(..., ge=1)
    estimated_word_count: int = Field(..., ge=1)
