"""
Book Generator FastAPI service.
Wraps the v2 pipeline for jnanalaya.nithyananda.ai/bookgenerator.

Endpoints:
  POST /upload              → parse transcript, create job → {job_id, title}
  GET  /jobs/{id}/stream    → SSE progress stream
  GET  /jobs/{id}/status    → current status JSON
  GET  /jobs/{id}/download  → completed .docx file
  GET  /jobs/{id}/preview   → completed .md as plain text
"""

from __future__ import annotations

import io
import json
import os
import queue
import re
import sys
import threading
import time
import uuid
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

# ── Thread-local stdout interceptor ────────────────────────────────────────
# Installed BEFORE importing workflow so all pipeline print() calls are captured
# per-thread into each job's progress queue.

_thread_local = threading.local()
_TRACE_RE    = re.compile(r'\[\d{2}:\d{2}:\d{2}\]')   # [16:02:14] trace lines
_SKIP_RE     = re.compile(r'^(WARNING|ERROR\s|={4,}|-{4,}|\s*$)')


class _CapturingStdout(io.RawIOBase):
    """Wraps sys.__stdout__. Progress lines are pushed to per-thread job queues."""
    _real = sys.__stdout__

    def write(self, s: str) -> int:          # type: ignore[override]
        n = self._real.write(s)
        q: Optional[queue.Queue] = getattr(_thread_local, 'job_queue', None)
        if q is not None:
            stripped = s.strip()
            if stripped and not _TRACE_RE.search(stripped) and not _SKIP_RE.match(stripped):
                q.put(stripped)
        return n

    def flush(self) -> None:
        self._real.flush()

    def isatty(self) -> bool:
        return False


sys.stdout = _CapturingStdout()  # type: ignore[assignment]

# ── Dependencies ────────────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')
load_dotenv(Path(__file__).parent.parent / '.env')

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from workflow import run_pipeline   # noqa: E402  (must come after stdout patch)


# ── Phase map ──────────────────────────────────────────────────────────────

PHASES = [
    ("intake",       "Intake",                      5),
    ("architect",    "Architect",                   12),
    ("research",     "Research",                    28),
    ("youtube",      "YouTube Matching",             33),
    ("writing",      "Writing",                     58),
    ("editing",      "Editing",                     72),
    ("qa",           "QA Review",                   80),
    ("qa_gen",       "Q&A Generation",               87),
    ("frontmatter",  "Foreword & Benediction",       93),
    ("designer",     "Designer",                    98),
]

_PHASE_KEY_MAP = {
    "Phase 1":           "intake",
    "Phase 2":           "architect",
    "Phase 3: Research": "research",
    "Phase 3.5":         "youtube",
    "Phase 4":           "writing",
    "Phase 5: Editing":  "editing",
    "Phase 5.5":         "qa",
    "Phase 5.55":        "qa_gen",
    "Phase 5.6":         "frontmatter",
    "Phase 6":           "designer",
}

_CHAPTER_RE = re.compile(r'Ch (\d+): Final=(\d+)w')
_TOTAL_RE   = re.compile(r'Total words\s*[:\-]\s*([\d,]+)')
_PAGES_RE   = re.compile(r'~(\d+)[–\-](\d+)\s*pages')


def _line_to_event(line: str, job: "Job") -> Optional[dict]:
    """Parse a pipeline print line into a structured SSE event dict."""

    # Phase transition
    for marker, key in _PHASE_KEY_MAP.items():
        if marker in line:
            pct = next((p for k, _, p in PHASES if k == key), job.progress)
            job.current_phase = key
            job.progress = pct
            label = next((l for k, l, _ in PHASES if k == key), key)
            return {"type": "phase", "key": key, "label": label, "progress": pct}

    # Chapter finished
    m = _CHAPTER_RE.search(line)
    if m:
        job.chapters_written += 1
        return {
            "type": "chapter",
            "number": int(m.group(1)),
            "words": int(m.group(2)),
            "total": job.total_chapters,
        }

    # Final stats
    m = _TOTAL_RE.search(line)
    if m:
        job.total_words = int(m.group(1).replace(",", ""))

    m = _PAGES_RE.search(line)
    if m:
        job.pages_low  = int(m.group(1))
        job.pages_high = int(m.group(2))

    # Generic detail message (keep short)
    if len(line) < 160:
        return {"type": "detail", "message": line}

    return None


# ── Job state ──────────────────────────────────────────────────────────────

@dataclass
class Job:
    job_id: str
    status: str          = "pending"   # pending | running | complete | error
    current_phase: str   = "intake"
    progress: int        = 0
    sync_queue: queue.Queue = field(default_factory=queue.Queue)
    docx_path: Optional[Path] = None
    md_path:   Optional[Path] = None
    title: str           = ""
    total_words: int     = 0
    pages_low: int       = 0
    pages_high: int      = 0
    error: Optional[str] = None
    created_at: float    = field(default_factory=time.time)
    chapters_written: int = 0
    total_chapters: int  = 8


_jobs: Dict[str, Job] = {}
_jobs_lock = threading.Lock()


def _get_job(job_id: str) -> Job:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Transcript text extraction ─────────────────────────────────────────────

def _extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")
    if ext == ".docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not parse .docx: {e}")
    if ext == ".doc":
        try:
            import mammoth
            result = mammoth.extract_raw_text(io.BytesIO(data))
            return result.value
        except ImportError:
            raise HTTPException(status_code=422, detail="mammoth is required to parse .doc files. Use .docx instead.")
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not parse .doc: {e}")
    raise HTTPException(status_code=422, detail=f"Unsupported file type: {ext}. Use .md, .txt, .docx, or .doc")


# ── Book config extraction from transcript ─────────────────────────────────

async def _extract_book_config(text: str) -> dict:
    """Call the NVIDIA API to extract a structured book config from the transcript."""
    from openai import AsyncOpenAI

    api_key  = os.environ.get("NVIDIA_API_KEY", "")
    base_url = "https://integrate.api.nvidia.com/v1"
    model    = "openai/gpt-oss-120b"

    if not api_key:
        # Fallback: use transcript as synopsis with a generic title
        return {
            "title": "Teachings of Paramashiva",
            "subtitle": "Wisdom from a Satsang of The SPH Bhagwan Sri Nithyananda Paramashivam",
            "synopsis": text[:1500],
            "themes": ["consciousness", "Paramashiva", "liberation", "Sanatana Hindu Dharma"],
            "verse_references": [],
            "num_chapters": 8,
        }

    client  = AsyncOpenAI(api_key=api_key, base_url=base_url)
    excerpt = text[:4000]

    prompt = f"""You are a spiritual book configuration extractor.
From the satsang transcript excerpt below, extract a complete book configuration.

Return ONLY valid JSON — no markdown fences, no explanation:
{{
  "title": "<evocative title in Living Enlightenment style — 4-8 poetic words>",
  "subtitle": "<descriptive subtitle — what the book reveals>",
  "synopsis": "<200-word synopsis of the book this transcript will inspire>",
  "themes": ["<theme 1>", "<theme 2>", "..."],
  "verse_references": ["<Sanskrit verse or sutra if found>", "..."],
  "num_chapters": 8
}}

Transcript excerpt:
{excerpt}"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        raw = resp.choices[0].message.content or ""
        m   = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            cfg = json.loads(m.group())
            cfg.setdefault("num_chapters", 8)
            return cfg
    except Exception as exc:
        print(f"Config extraction error: {exc}", file=sys.__stdout__)

    # Fallback on any failure
    return {
        "title": "The Teaching Revealed",
        "subtitle": "A Spiritual Book from The SPH Bhagwan Sri Nithyananda Paramashivam",
        "synopsis": text[:1500],
        "themes": ["consciousness", "Paramashiva", "liberation"],
        "verse_references": [],
        "num_chapters": 8,
    }


def _config_to_book_input(cfg: dict, transcript_text: str) -> dict:
    themes = cfg.get("themes", [])
    if "Paramashiva as inner reality" not in themes:
        themes = list(themes) + [
            "Paramashiva as inner reality",
            "Sanatana Hindu Dharma",
            "living enlightenment",
        ]
    return {
        "title":            cfg["title"],
        "subtitle":         cfg.get("subtitle", ""),
        "author":           "The SPH Bhagwan Sri Nithyananda Paramashivam",
        "num_chapters":     int(cfg.get("num_chapters", 8)),
        "words_per_chapter": 2500,
        "pov":              "first person",
        "tone":             "spiritual-conversational",
        "reading_level":    "intermediate",
        "language":         "English",
        "synopsis":         cfg.get("synopsis", transcript_text[:1500]),
        "themes":           themes[:12],
        "target_audience":  "Spiritual seekers, Hindu devotees, and meditators",
        "reference_sources": [
            "https://jnanalaya.kailasa.ai/mcp",
            "https://jnanalaya.nithyananda.ai/mcp",
        ],
        "section_template": [
            "opening_story",
            "teaching",
            "practical_exercise",
            "humor",
            "closing_bridge",
        ],
        "include_foreword":    True,
        "include_benediction": True,
        "include_toc":         True,
    }


# ── Pipeline runner (background thread) ───────────────────────────────────

def _run_pipeline_thread(job: Job, book_input: dict) -> None:
    """Run the full pipeline in its own thread + event loop."""
    _thread_local.job_queue = job.sync_queue
    job.status = "running"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        state = loop.run_until_complete(run_pipeline(book_input))

        job.docx_path   = state.docx_path
        job.total_words = sum(c.final_word_count for c in state.edited.values())
        fw_wc  = len(getattr(state, "_foreword", "").split())
        be_wc  = len(getattr(state, "_benediction", "").split())
        grand  = job.total_words + fw_wc + be_wc
        job.total_words = grand
        job.pages_low   = round(grand / 320)
        job.pages_high  = round(grand / 280)

        # Locate the .md counterpart
        if state.docx_path:
            md_candidate = state.docx_path.with_suffix(".md")
            if md_candidate.exists():
                job.md_path = md_candidate

        job.progress = 100
        job.status   = "complete"
        job.sync_queue.put(
            f"BOOK_COMPLETE words={grand} pages_low={job.pages_low} pages_high={job.pages_high}"
        )

    except Exception as exc:
        job.status = "error"
        job.error  = str(exc)
        job.sync_queue.put(f"BOOK_ERROR {exc}")
        print(f"Pipeline error for job {job.job_id}: {exc}", file=sys.__stdout__)
    finally:
        _thread_local.job_queue = None
        try:
            loop.close()
        except Exception:
            pass


# ── FastAPI app ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Book Generator API",
    description="Generates spiritual books from satsang transcripts",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://jnanalaya.nithyananda.ai",
        "http://localhost:3000",
        "http://localhost:7045",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ── POST /upload ───────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_transcript(file: UploadFile = File(...)):
    """
    Accept a transcript file (.md, .txt, .docx, .doc),
    extract a book config with the LLM, start the pipeline.
    Returns {job_id, title, num_chapters}.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    data = await file.read()
    if len(data) > 50 * 1024 * 1024:  # 50 MB cap
        raise HTTPException(status_code=413, detail="File too large (max 50 MB).")

    text = _extract_text(file.filename, data)
    if len(text.strip()) < 100:
        raise HTTPException(status_code=422, detail="Transcript too short (< 100 chars).")

    cfg        = await _extract_book_config(text)
    book_input = _config_to_book_input(cfg, text)

    job_id = str(uuid.uuid4())
    job    = Job(
        job_id=job_id,
        title=book_input["title"],
        total_chapters=book_input["num_chapters"],
    )
    with _jobs_lock:
        _jobs[job_id] = job

    t = threading.Thread(
        target=_run_pipeline_thread,
        args=(job, book_input),
        daemon=True,
        name=f"pipeline-{job_id[:8]}",
    )
    t.start()

    return {
        "job_id":       job_id,
        "title":        book_input["title"],
        "subtitle":     book_input.get("subtitle", ""),
        "num_chapters": book_input["num_chapters"],
    }


# ── GET /jobs/{id}/stream (SSE) ────────────────────────────────────────────

@app.get("/jobs/{job_id}/stream")
async def stream_progress(job_id: str):
    """Server-Sent Events stream of pipeline progress."""
    job = _get_job(job_id)

    async def _generator():
        event_id   = 0
        last_phase = None

        while True:
            try:
                line = job.sync_queue.get_nowait()
            except queue.Empty:
                if job.status in ("complete", "error"):
                    # Final event
                    if job.status == "complete":
                        payload = {
                            "type":       "complete",
                            "words":      job.total_words,
                            "pages_low":  job.pages_low,
                            "pages_high": job.pages_high,
                        }
                    else:
                        payload = {"type": "error", "message": job.error or "Unknown error"}
                    yield f"id: {event_id}\ndata: {json.dumps(payload)}\n\n"
                    return
                # Heartbeat — keeps proxy / browser connection alive
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.4)
                continue

            # Parse line → structured event
            evt = _line_to_event(line, job)
            if evt is None:
                continue

            # Suppress duplicate phase events
            if evt["type"] == "phase":
                if evt["key"] == last_phase:
                    continue
                last_phase = evt["key"]

            yield f"id: {event_id}\ndata: {json.dumps(evt)}\n\n"
            event_id += 1

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


# ── GET /jobs/{id}/status ──────────────────────────────────────────────────

@app.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    job = _get_job(job_id)
    return {
        "job_id":           job.job_id,
        "status":           job.status,
        "current_phase":    job.current_phase,
        "progress":         job.progress,
        "title":            job.title,
        "total_words":      job.total_words,
        "pages_low":        job.pages_low,
        "pages_high":       job.pages_high,
        "chapters_written": job.chapters_written,
        "total_chapters":   job.total_chapters,
        "error":            job.error,
    }


# ── GET /jobs/{id}/download ────────────────────────────────────────────────

@app.get("/jobs/{job_id}/download")
async def download_book(job_id: str):
    job = _get_job(job_id)
    if job.status != "complete":
        raise HTTPException(status_code=425, detail="Book not ready yet.")
    if not job.docx_path or not job.docx_path.exists():
        raise HTTPException(status_code=404, detail="DOCX file not found.")

    safe_title = re.sub(r'[^\w\s-]', '', job.title)[:60].strip().replace(' ', '_')
    return FileResponse(
        path=str(job.docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{safe_title}.docx",
    )


# ── GET /jobs/{id}/preview ─────────────────────────────────────────────────

@app.get("/jobs/{job_id}/preview")
async def preview_book(job_id: str):
    job = _get_job(job_id)
    if job.status != "complete":
        raise HTTPException(status_code=425, detail="Book not ready yet.")
    if job.md_path and job.md_path.exists():
        return StreamingResponse(
            open(job.md_path, "r", encoding="utf-8"),
            media_type="text/plain; charset=utf-8",
        )
    raise HTTPException(status_code=404, detail="Markdown preview not available.")


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
