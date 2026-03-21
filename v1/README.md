# 📚 KAILASA Agentic Book Generation Pipeline

Generates complete spiritual books inspired by **Living Enlightenment**, powered by
two live MCP sources and four specialized agents.

---

## 🔌 MCP Sources

| MCP Server | URL | Used For |
|---|---|---|
| Kailasa Jnanalaya | `jnanalaya.kailasa.ai/mcp` | Living Enlightenment structure, style, and chapter reference |
| SPH Books | `jnanalaya.nithyananda.ai/mcp` | Verse / sutra quotes anchoring each chapter |

---

## 🏛️ Agent Architecture

```
Topic Input (interactive prompt)
          │
          ▼
┌─────────────────────────────────────────────────────┐
│              BOOK ADMINISTRATOR                      │
│           (Mistral Large — Team Leader)              │
│   TeamMode.tasks · micromanages · compiles final    │
└─────┬──────────────┬──────────────┬─────────────────┘
      │              │              │
   Phase 1        Phase 2        Phase 3
      ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│  Book    │  │  Book    │  │    Book      │
│ Designer │→ │  Writer  │→ │ Proofreader  │
│          │  │          │  │              │
│ MCP: LE  │  │ MCP: LE  │  │ MCP: verify  │
│ structure│  │  style   │  │   verses     │
│ + verse  │  │ + verses │  │              │
│  refs    │  │ + jokes  │  │              │
└──────────┘  └──────────┘  └──────────────┘
                                    │
                                 Phase 4
                                    ▼
                         ┌──────────────────┐
                         │  COMPILED BOOK   │
                         │  output/*.md     │
                         └──────────────────┘
```

---

## 📖 What each chapter contains

Every chapter is written to mirror **Living Enlightenment**:

1. **Opening story** — a vivid teaching narrative (300–500 words)
2. **Core teaching** — the chapter's central insight
3. **Verse anchor** — a sutra/quote fetched live from SPH Books MCP
4. **Practical exercise** — a contemplation or sadhana for the reader
5. **1–2 jokes** — light, spiritually relevant humor woven into the text
6. **Chapter bridge** — closing paragraph linking to the next chapter

---

## ⚡ Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set NVIDIA API key (from build.nvidia.com)
export NVIDIA_API_KEY="nvapi-..."

# 3. Run — the script will ask you for the book topic
python book_workflow.py
```

Example session:
```
══════════════════════════════════════════════════════════════════════
  📚  KAILASA Agentic Book Generation Pipeline
══════════════════════════════════════════════════════════════════════

  This pipeline will generate a complete spiritual book inspired by
  'Living Enlightenment', enriched with verse references from
  SPH Bhagavan Sri Nithyananda Paramashivam's teachings.

  🔷  What topic should the book be about?
  ➜  The science of Nithya Dhyaan meditation
```

---

## 🔧 Changing the Mistral model

In `book_workflow.py`, update these two lines:

```python
LEAD_MODEL  = Nvidia(id="mistralai/mistral-large-latest")   # Administrator
AGENT_MODEL = Nvidia(id="mistralai/mistral-large-latest")   # Sub-agents
```

Other options from build.nvidia.com:
- `mistralai/mixtral-8x22b-instruct-v0.1` — largest / most capable
- `mistralai/mixtral-8x7b-instruct-v0.1`  — fast, efficient
- `mistralai/mistral-7b-instruct-v0.3`    — lightest / cheapest

---

## 🛠️ MCP Transport Notes

Both servers use `streamable-http` transport (Payload CMS MCP standard).
If you see connection errors, try switching to `sse`:

```python
jnanalaya_tools = MCPTools(transport="sse", url=JNANALAYA_MCP_URL)
```
