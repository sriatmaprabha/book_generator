# Book Generator v2

Multi-agent AI pipeline for generating spiritually authentic books in the voice of **The SPH Bhagwan Sri Nithyananda Paramashivam**, modeled on the *Living Enlightenment* style. Also includes a **satsang transcript compiler** that preserves every word while adding structure, shastra pramanas, and humor.

## Architecture Overview

```
                          ┌─────────────┐
                          │  User Input  │
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │   Intake    │  Validates BookConfig
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │  Architect  │  Designs BookBlueprint
                          └──────┬──────┘  (chapter briefs, arcs, seeds)
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐┌──────────┐┌──────────┐
              │Researcher││Researcher││Researcher│  Parallel per chapter
              │  Ch.1    ││  Ch.2    ││  Ch.N    │  (MCP: Kailasa + SPH)
              └────┬─────┘└────┬─────┘└────┬─────┘
                   │           │           │
          ┌────────▼───────────▼───────────▼────────┐
          │              Per Chapter                  │
          │  ┌─────────────┐  ┌──────────────────┐  │
          │  │Story Writer │  │ Content Writer   │  │  Parallel
          │  │(Living Enl. │  │(Teaching,Exercise│  │
          │  │ style)      │  │ Humor, Bridge)   │  │
          │  └──────┬──────┘  └───────┬──────────┘  │
          │         └────────┬────────┘              │
          │           ┌──────▼──────┐                │
          │           │  Combiner   │  Merges with   │
          │           │  Writer     │  transitions   │
          │           └──────┬──────┘                │
          └──────────────────┼──────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Editor (x N)   │  Parallel per chapter
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   QA Reviewer   │──── Fail? ──→ Rewrite Loop
                    └────────┬────────┘               (Story+Content+
                             │ Pass                    Combiner+Editor)
                    ┌────────▼────────┐
                    │    Designer     │  .docx + .md
                    └─────────────────┘
```

## Two Pipelines

### 1. Creative Book Generator (`full_run.py`, `main.py`)

Generates original books from a topic prompt. The AI writes every word — stories, teachings, exercises, humor — in Swamiji's authentic voice.

```bash
python full_run.py          # asks for topic, generates 7-chapter book
python main.py              # interactive mode (all fields customizable)
python main.py --input book.json   # from JSON spec
```

### 2. Satsang Transcript Compiler (`compile_satsang.py`)

Compiles existing satsang transcripts into a structured book. **Preserves every spoken word** while adding formatting, shastra pramanas, humor stories, and grammar corrections.

```bash
python compile_satsang.py --dir transcripts_feb2026
```

## Quick Start

### Prerequisites

```bash
pip install agno>=2.5.10 pydantic>=2.0 openai>=1.0 python-docx>=1.1.0 pyyaml>=6.0
```

### Configuration

Edit `v2/config.yaml`:

```yaml
defaults:
  model: "openai/gpt-oss-120b"
  base_url: "https://integrate.api.nvidia.com/v1"
  api_key: "your-api-key-here"

agents:
  intake:     { max_tokens: 2048 }
  architect:  { max_tokens: 8192 }
  researcher: { max_tokens: 16384 }
  writer:     { max_tokens: 12288 }
  editor:     { max_tokens: 10240 }
  qa:         { max_tokens: 16384 }
  designer:   { max_tokens: 4096 }
```

Any OpenAI-compatible endpoint works (NVIDIA, OpenRouter, local vLLM, etc.).

### Run

```bash
cd v2
python full_run.py
# > What topic should the book be written on?
# > Does Shiva Reside Inside Me?
```

Output appears in `v2/output/{title}_{timestamp}/`:
- `{title}.docx` — styled Word document
- `{title}.md` — combined markdown
- `agent_traces.log` — full agent input/output trace
- `blueprint.json` — chapter plan
- `chapters/` — individual chapter files
- `qa_review_round1.json` — QA scores

## Agents

| Agent | Role | Tools | Parallel |
|-------|------|-------|----------|
| **Intake** | Validates user input into `BookConfig` | None | - |
| **Architect** | Designs `BookBlueprint` with chapter briefs | MCP (optional) | - |
| **Researcher** | Gathers shastra references per chapter | MCP (per-agent pool) | Yes |
| **Story Writer** | Writes opening story (Living Enlightenment style) | None | Yes (with Content) |
| **Content Writer** | Writes teaching, exercise, humor, bridge | None | Yes (with Story) |
| **Combiner** | Merges story + content with transitions | None | - |
| **Editor** | Polishes, expands thin sections, verifies Sanskrit | None | Yes |
| **QA Reviewer** | Scores voice/structure/shastra/story; triggers rewrites | MCP (optional) | - |
| **Designer** | Builds styled `.docx` from final chapters | None | - |

## Voice Profile

Every agent writes in the voice of **The SPH Bhagwan Sri Nithyananda Paramashivam** (Swamiji):

- First person Guruvaak — direct transmission, not opinion
- Fierce compassion for Sanatana Hindu Dharma
- Vivid earthy metaphors (cooking, driving, relationships)
- Key phrases: *"Understand..."*, *"I tell you..."*, *"Listen..."*, *"In Sanatana Hindu Dharma, we say..."*
- Sanskrit terms with inline English: *"your ahamkara, your ego identity"*
- Humor from real-life incidents — ashram stories, devotee encounters
- Exact Sanskrit shlokas with source + translation

## Story Formats

Modeled on *Living Enlightenment*, stories vary across chapters:

| Format | Style | Example |
|--------|-------|---------|
| **A. Short Parable** | 2-3 paragraphs, italicized, punchline | *"A disciple said, 'I can't meditate.' The master said, 'It will pass.'"* |
| **B. Autobiographical** | 4-6 paragraphs, first person, sensory | *"In my wandering days, I had been to Varanasi..."* |
| **C. Devotee Encounter** | 3-5 paragraphs, dialogue-driven | *"Once a person went to the great saint Ramanuja and asked..."* |
| **D. Real-life Incident** | 3-4 paragraphs, universal moment | *"A girl afraid to cross the street sees her child run across..."* |

## QA Scoring

Each chapter scored 1-10 on four dimensions:

| Score | Criteria |
|-------|----------|
| **voice_score** | Does it sound like Swamiji in Living Enlightenment? |
| **structure_score** | All sections present with depth? |
| **shastra_score** | Sanskrit verses exact, properly cited? |
| **story_score** | Immersive, varied formats, sensory, named characters? |

Pass threshold: all scores >= 6. Failing chapters auto-rewrite through the full Story+Content+Combiner+Editor pipeline.

## Satsang Compiler Pipeline

For compiling existing satsang transcripts (preserving every word):

```
Ingest → Structure → Shastra Enrichment → Humor Stories
  → Deterministic Format (case conversion, no LLM)
  → Grammar Correction → QA → Designer
```

Key features:
- **Zero word loss**: deterministic formatter, no LLM in main pass
- **ALL CAPS → Sentence Case**: 200+ Sanskrit terms preserved with correct casing
- **Sanskrit verse detection**: auto-block-quoted with diacritical recognition
- **Section breaks**: inserted at discourse markers ("Listen.", "Understand.")
- **Humor insertion**: Living Enlightenment-style parables added per chapter
- **Shastra enrichment**: Sanskrit verses from MCP sources + LLM generation

## MCP Sources

| Source | URL | Tool Names | Content |
|--------|-----|------------|---------|
| Kailasa Jnanalaya | `jnanalaya.kailasa.ai/mcp` | `search-books`, `resolve-book`, `get-chapters`, `read-chapter` (HYPHENS) | Vedic texts, Upanishads, Agamas |
| SPH Books | `jnanalaya.nithyananda.ai/mcp` | `search_chapters`, `get_chapter`, `list_books` (UNDERSCORES) | Swamiji's published works, Living Enlightenment |
| Nithyanandapedia | `nithyanandapedia.nithyananda.ai/mcp` | `get_satsangs`, `search`, `get_document` | Satsang transcripts, programs, daily summaries |

## Tracing

Every agent call is traced to two files:

- **`agent_traces.jsonl`** — machine-readable (one JSON per agent call)
- **`agent_traces.log`** — human-readable with full input/output

Each trace includes: agent name, phase, timestamp, duration, full instructions, prompt, raw response, parsed output, success status, errors.

Console shows live progress:
```
[14:02:01] Writer-Ch2 > StoryWriter (Ch.2) | START: prompt=70 chars
[14:02:09] Writer-Ch2 > StoryWriter (Ch.2) | OK: 596w, 8.2s
```

Summary table at completion:
```
Agent                      Phase           Duration  Status  Output
──────────────────────────────────────────────────────────────────────
Architect Agent            Architect          38.1s  OK      BookBlueprint
Researcher (Ch.1)          Research-Ch1       19.6s  OK      ResearchPacket
StoryWriter (Ch.1)         StoryWriter-Ch1    10.8s  OK      str
...
TOTAL                                        822.8s
```

## File Structure

```
book_generator/
├── v1/                          # Legacy single-agent pipeline
│   ├── agno_book_workflow.py
│   ├── book_workflow.py
│   └── requirements.txt
│
├── v2/                          # Multi-agent pipeline
│   ├── config.yaml              # Central config (models, MCP, settings)
│   ├── config.py                # Config loader + model factory
│   ├── models.py                # All Pydantic data models
│   ├── agents.py                # 9 agent definitions + SWAMIJI_VOICE
│   ├── workflow.py              # Creative book pipeline orchestrator
│   ├── compile_satsang.py       # Satsang transcript compiler
│   ├── tracing.py               # Agent call tracing
│   ├── main.py                  # Interactive CLI
│   ├── full_run.py              # Topic-based 7-chapter generator
│   ├── run_shiva.py             # "Does Shiva Reside Inside Me?" preset
│   ├── test_run.py              # Quick 3-chapter validation test
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

## Example Output

**"Does Shiva Reside Inside Me?"** — 7 chapters, 16,499 words, QA approved round 1:

| Chapter | Title | Words | Voice | Structure | Shastra | Story |
|---------|-------|-------|-------|-----------|---------|-------|
| 1 | The Seed of Doubt — 'Am I Worthy of Shiva?' | 2,303 | 9 | 9 | 8 | 8 |
| 2 | The Living Mirror — The Guru as Shiva's Reflection | 2,086 | 9 | 9 | 8 | 8 |
| 3 | Peeling the Sheaths — The Five Koshas | 2,382 | 8 | 9 | 8 | 8 |
| 4 | The Breath of Shiva — Practicing Shiva-Consciousness | 2,249 | 9 | 9 | 8 | 9 |
| 5 | Shivoham — The Declaration 'I Am Shiva' | 2,588 | 9 | 9 | 8 | 9 |
| 6 | Living Shiva — Integrating the Divine in Daily Life | 2,474 | 8 | 9 | 8 | 9 |
| 7 | The Dawn of Direct Realization | 2,417 | 9 | 9 | 8 | 9 |

**Satsang Compilation** — 7 transcripts, 52,090 words, -0.8% metadata loss only:

| Chapter | Day | Date | Original | Final |
|---------|-----|------|----------|-------|
| 1 | Day 1 | 06 Feb 2026 | 6,630w | 6,598w |
| 2 | Day 2 | 07 Feb 2026 | 7,476w | 7,463w |
| 3 | Day 3 | 08 Feb 2026 | 6,350w | 6,340w |
| 4 | Day 5 | 10 Feb 2026 | 6,434w | 6,343w |
| 5 | Day 8 | 13 Feb 2026 | 6,841w | 6,700w |
| 6 | Day 9 | 14 Feb 2026 | 4,329w | 4,401w |
| 7 | Day 10 | 15 Feb 2026 | 14,030w | 13,811w |
