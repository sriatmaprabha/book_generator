# Book Generator — Changes Walkthrough

All changes are in [agno_book_workflow.py](file:///d:/book_generator/agno_book_workflow.py). Syntax verified ✅

---

## 1 — Token Limit & Depth Constants

```diff
-MAX_AGENT_OUTPUT_TOKENS = int(os.getenv("BOOK_AGENT_MAX_TOKENS", "4096"))
+MAX_AGENT_OUTPUT_TOKENS = int(os.getenv("BOOK_AGENT_MAX_TOKENS", "8192"))
 MIN_CHAPTERS = 7
 MAX_CHAPTERS = 10
 MAX_STAGE_RETRIES = 2
+# Chapter depth targets
+MIN_CHAPTER_WORDS = 2000
+MAX_CHAPTER_WORDS = 3500
+MIN_SECTION_PARAGRAPHS = 3
```

**Why:** 4096 tokens was the primary reason chapters were tiny (~2KB). 8192 allows the LLM to write a full literary chapter. The new constants flow through validation, prompts, and agent instructions.

---

## 2 — ChapterBrief Model Extended

```diff
 class ChapterBrief(BaseModel):
     number: int = Field(..., ge=1)
     title: str
     core_teaching: str
-    story_seed: str
+    story_seed: str           # 3+ sentence narrative seed
+    narrative_arc: str        # multi-sentence teaching progression arc
     verse_reference: str
-    joke_seed: str
-    bridge_to_next: str
+    joke_seed: str            # warm anecdote seed (NOT a punchline)
+    bridge_to_next: str       # narrative hook to next chapter
+    target_word_count: int = Field(default=2500, ge=MIN_CHAPTER_WORDS, le=MAX_CHAPTER_WORDS)
```

**Why:** The designer was generating one-liner seeds. Making `narrative_arc` and `target_word_count` explicit fields forces the LLM to populate them with real content, which the writer and proofreader then use.

---

## 3 — Chapter Validation (word count threshold)

```diff
-    if chapter.word_count < 700:
-        issues.append(f"Chapter {expected_number} is too short to be a complete chapter.")
+    if chapter.word_count < MIN_CHAPTER_WORDS:
+        issues.append(
+            f"Chapter {expected_number} is too short ({chapter.word_count} words). "
+            f"Minimum required: {MIN_CHAPTER_WORDS} words. Each section needs {MIN_SECTION_PARAGRAPHS}+ paragraphs."
+        )
```

**Why:** Lifting the bar from 700 to 2000 words means the Administrator will reject thin chapters and trigger rewrites.

---

## 4 — Designer Agent Instructions

````diff
- "Every chapter needs a story seed, a teaching arc, a verse anchor, a joke seed, and a bridge..."
- "Set tone, speech level, speech style, and joke policy clearly..."
+ "For EACH chapter brief you MUST provide:"
+ "  - story_seed: AT LEAST 3 sentences describing protagonist, setting, conflict, turning point"
+ "  - narrative_arc: 3-5 sentences tracing teaching progression"
+ "  - joke_seed: A 2-3 sentence warm storytelling scenario (NOT a punchline)"
+ "  - bridge_to_next: 2-3 sentences creating narrative tension"
+ "  - target_word_count: 2500 for standard chapters, 3000 for key chapters"
````

**Why:** The old instruction was a vague list. Now each field has a quantity requirement and a description of quality expected.

---

## 5 — Writer Agent Instructions (biggest change)

The writer now has **section-by-section word and paragraph targets**:

```diff
- "Each chapter must include: Opening Story, The Teaching, Practical Exercise, Humor, Closing Bridge."
- "Integrate one warm joke or witty observation naturally."
+
+ f"Every chapter MUST be between {MIN_CHAPTER_WORDS} and {MAX_CHAPTER_WORDS} words total."
+ f"Every section MUST contain at least {MIN_SECTION_PARAGRAPHS} substantial paragraphs (80+ words each)."
+ "  ### Opening Story (target 400-500 words): Complete short story — vivid setting, named protagonist,
+     inciting incident, internal struggle, turning point, resolution."
+ "  ### The Teaching (target 600-800 words): Quote and unpack verse, layer 3-4 building insights,
+     real-world analogies, close with enlightenment statement."
+ "  ### Practical Exercise (target 350-500 words): Name the practice. Intention paragraph,
+     5+ numbered steps (2+ sentences each), 'what you may notice', 'common pitfalls'."
+ "  ### Humor (target 250-350 words): 3-4 paragraph warm anecdote — NOT a one-liner.
+     Self-deprecating, spiritually aware, lands at a gentle insight."
+ "  ### Closing Bridge (target 200-300 words): Reflect on shift, pose open question,
+     gesture toward next chapter's theme."
```

---

## 6 — Proofreader Agent Instructions

```diff
- "Polish the chapter without changing its intent..."
- "Tighten grammar, clarity, pacing..."
+ "FIRST check depth before polishing:"
+ f"  - If any section < {MIN_SECTION_PARAGRAPHS} paragraphs → EXPAND it"
+ f"  - If chapter total < {MIN_CHAPTER_WORDS} words → expand thinnest sections first"
+ "THEN polish: grammar, verse quoting, humor style (must be anecdote not punchline),
+   Closing Bridge narrative hook."
```

**Why:** The proofreader was only polishing — never expanding. Now it's the safety net that catches thin sections the writer missed.

---

## 7 — Proofreader Prompt: markdown text instead of JSON dump

```diff
-        Current chapter draft:
-        {draft.model_dump_json(indent=2)}
+        Current chapter draft (markdown):
+        {draft.markdown}
```

**Why:** Passing `model_dump_json` added ~40% overhead with metadata the proofreader never used. Passing `draft.markdown` directly keeps the context clean and costs fewer tokens.

---

## 8 — Designer Prompt: Explicit Field Requirements

```diff
+ CRITICAL FIELD REQUIREMENTS for each chapter brief:
+ - story_seed: Minimum 3 sentences...
+ - narrative_arc: Minimum 3 sentences...
+ - joke_seed: A 2-3 sentence warm storytelling scenario (NOT a punchline)...
+ - bridge_to_next: 2-3 sentences creating narrative tension...
+ - target_word_count: 2500 standard, 3000 pivotal chapters
```

---

## 9 — Writer Prompt: Rolling Chapter Summaries

```diff
+    prior_context_block = ""
+    if prior_chapter_summaries:
+        prior_lines = "\n".join(f"  - {s}" for s in prior_chapter_summaries)
+        prior_context_block = f"Previously written chapters (maintain continuity):\n{prior_lines}"
+
+ TARGET: {chapter_brief.target_word_count} words for this chapter.
+ Every section MUST have at least {MIN_SECTION_PARAGRAPHS} substantial paragraphs.
+
+ {prior_context_block}
```

Both [write_chapters_loop](file:///d:/book_generator/agno_book_workflow.py#1036-1065) and [WriteChaptersExecutor](file:///d:/book_generator/agno_book_workflow.py#1333-1362) now accumulate:
```python
prior_summaries.append(f"Ch {chapter_brief.number} '{draft.title}': {draft.summary}")
```

**Why:** Previously each chapter was written in a vacuum. Now Chapter 4 knows what Chapters 1-3 said, so it can build on them rather than repeat.

---

## 10 — Progress Logging

```diff
-    print(f"    Writing chapter {chapter_brief.number}/{blueprint.chapter_count}...")
+    print(f"    Writing chapter {chapter_brief.number}/{blueprint.chapter_count} (target {chapter_brief.target_word_count} words)...")
+    print(f"      → {draft.word_count} words written.")
```

---

## Summary Table

| Area | Before | After |
|---|---|---|
| Token limit | 4096 | **8192** |
| Min chapter words | 700 | **2000** |
| story_seed | 1 sentence | **3+ sentences** |
| narrative_arc | ❌ missing | **✅ new field** |
| target_word_count | ❌ missing | **✅ per chapter** |
| Writer section targets | None | **5 sections × word targets** |
| Humor type | Punchline jokes | **Warm 3-4 para anecdotes** |
| Proofreader role | Polish only | **Expand thin + polish** |
| Chapter continuity | Isolated | **Rolling summaries** |
| Proofreader context | Full JSON dump | **Markdown only** |
