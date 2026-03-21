# Agno Book Generator: Quality Improvement Plan

## Problem Summary

The current workflow produces **very thin chapters** (~2KB, ~11 lines each) with shallow content, single-paragraph sections, and generic spiritual text. Key root causes:

1. **Token limits are too low** (`MAX_AGENT_OUTPUT_TOKENS = 4096`) — not enough for long-form literary chapters
2. **Agent instructions are vague** — no explicit word count minimums, no depth requirements
3. **Writer prompts lack targets** — no "write at least 2000 words with 5+ paragraphs per section"
4. **No continuity between chapters** — each chapter is written in isolation with no awareness of what came before
5. **Blueprint is too shallow** — `story_seed`, `teaching arc`, `joke_seed` are one-liners; they need to be multi-sentence narrative seeds
6. **Proofreader doesn't expand** — it's told to "polish" not to "expand thin sections to meet depth targets"
7. **No enrichment layer** — there's no agent that checks for and fills in surface-level sections
8. **Humor is not warm** — jokes are simple punchlines, not the warm storytelling humor of Living Enlightenment

## Proposed Changes

---

### Core Configuration

#### [MODIFY] [agno_book_workflow.py](file:///d:/book_generator/agno_book_workflow.py)

**Constants:**
- Raise `MAX_AGENT_OUTPUT_TOKENS` from `4096` → `8192` (allows full long-form chapters)
- Add `MIN_CHAPTER_WORDS = 2000` and `MAX_CHAPTER_WORDS = 3500` constants
- Add `MIN_SECTION_PARAGRAPHS = 3` constant for enforcing section depth

**Data Models:**
- Add `target_word_count: int` and `narrative_arc: str` fields to [ChapterBrief](file:///d:/book_generator/agno_book_workflow.py#50-58)
- Expand [chapter_issues()](file:///d:/book_generator/agno_book_workflow.py#280-300) to validate minimum word counts against `MIN_CHAPTER_WORDS`

**Designer Agent & Prompt:**
- Write much richer system instructions: demand multi-sentence story seeds, full narrative arcs, detailed teaching progressions, and warm humorous anecdotes (not punchlines)
- Designer prompt now includes: explicit chapter word count targets, section-depth requirements (3+ paragraphs per section), and requirement for narrative continuity hooks

**Writer Agent & Prompt:**
- Completely rewrite system instructions:
  - "Write each section with at least 3 rich paragraphs (100+ words each)"
  - "The Opening Story must be a full short story: setting, conflict, turning point, resolution (300-400 words)"
  - "The Teaching must weave verse, real-world application, and multiple sub-examples (500+ words)"
  - "Practical Exercise must have: intention, detailed steps, what to notice, common pitfalls (300+ words)"
  - "Humor must be a warm anecdote or self-deprecating story, not a one-liner punchline"
  - "Closing Bridge must preview the next chapter through a narrative hook (150+ words)"
- Writer prompt now passes **previous chapter summaries** for continuity (rolling list grows as chapters are written)

**New: `ContentEnricher` Agent (new step between writer and proofreader):**
- Purpose: receives a chapter and checks each section against depth targets; expands any section under 3 paragraphs
- Instructions: "You are a content depth reviewer. For each section, if it contains fewer than 3 paragraphs, expand it with richer narrative, additional examples, or deeper insight. Do not remove content."
- Add `enrich_chapters_loop` step to the Workflow steps list

**Proofreader Agent & Prompt:**
- Rewrite instructions to include: "If a section is thin (fewer than 3 paragraphs), add depth before polishing"
- Proofreader now receives the `narrative_arc` from the chapter brief for alignment
- Only the chapter [markdown](file:///d:/book_generator/agno_book_workflow.py#214-228) field is passed (not the full `model_dump()`) to save context

**Writer loop — rolling chapter summaries:**
- After each chapter is written, store its `summary` in a running list
- Each subsequent chapter's prompt includes a `"Previously written chapters:"` block listing the prior chapter titles and summaries

**Administrator review prompts:**
- Add heuristic: reject any chapter with `word_count < MIN_CHAPTER_WORDS`
- Add to admin instructions: "Reject any blueprint chapter brief with a story_seed under 3 sentences"

---

## Verification Plan

### Manual Verification
Run the improved script on a test topic and check output metrics:

```bash
cd d:\book_generator
python agno_book_workflow.py
# Enter topic: "The inner science of conscious living"
```

Then check:
1. **Word counts**: Each chapter file in `output/*/draft/chapters/*.md` should be 2000+ words
2. **Section depth**: Each section (`### Opening Story`, etc.) should have 3+ paragraphs
3. **Humor quality**: Should be an anecdote, not a 1-liner joke
4. **Continuity**: Chapter 3+ should reference/build on earlier chapters
5. **Blueprint richness**: [blueprint.md](file:///d:/book_generator/output/witness_the_witnesser_and_observe_the_observer_20260318_140752/blueprint.md) story seeds should be multi-sentence narratives

> [!NOTE]
> No automated tests exist in the project. Verification is manual inspection of output quality.

> [!IMPORTANT]
> The `NVIDIA_API_KEY` environment variable must be set before running. The workflow auto-selects the best available model from `MODEL_CANDIDATES`.
