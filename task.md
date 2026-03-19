# Book Generator Improvement Task

## Analysis Phase
- [x] Read [agno_book_workflow.py](file:///d:/book_generator/agno_book_workflow.py) (1550 lines) fully
- [x] Inspect output structure and sample chapter drafts
- [x] Read blueprint output
- [x] Research agno best practices via Context7 / docs

## Identified Quality Issues
- [x] Chapters are extremely thin (~2KB, ~11 lines) - target should be 2000+ words
- [x] `MAX_AGENT_OUTPUT_TOKENS = 4096` is too low for long-form chapters
- [x] Agent instructions are generic and don't demand sufficient depth
- [x] Writer agent has no word count targets in prompts
- [x] Blueprint `story_seed` and teaching fields are very brief - need richer seeding
- [x] Proofreader receives entire [ChapterDraft](file:///d:/book_generator/agno_book_workflow.py#78-84) JSON but the markdown is what matters
- [x] No use of `show_tool_calls` or reasoning traces during development
- [x] Humor sections are just simple punchline jokes, not warm storytelling humor
- [x] No use of `reasoning=True` or structured thinking for complex writing tasks
- [x] Designer agent builds chapters in isolation without seeing prior chapters for consistency

## Planning Phase
- [/] Write implementation plan

## Execution Phase
- [ ] Increase token limits and update model constants
- [ ] Rewrite deeply detailed agent system instructions
- [ ] Add explicit word-count targets and section depth requirements to prompts
- [ ] Add per-chapter context window with previous chapter summaries for continuity
- [ ] Improve blueprint model: richer story seeds, multi-paragraph teaching arcs
- [ ] Add `ChapterBrief.target_word_count` field
- [ ] Improve proofreader to focus on expanding thin sections
- [ ] Add a `ContentEnricher` agent step between writer and proofreader
- [ ] Improve chapter assembly for better flow
- [ ] Update [requirements.txt](file:///d:/book_generator/requirements.txt) if needed

## Verification Phase
- [ ] Run a test generation on a known topic
- [ ] Check output word counts against targets
- [ ] Review chapter structural quality
