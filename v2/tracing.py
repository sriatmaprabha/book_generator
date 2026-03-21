"""
Agent tracing — logs full input prompts, instructions, and outputs for every agent call.

Writes to:
  - Console: summarized progress with key metrics
  - Trace file: full detail (prompt, instructions, raw response, parsed output)
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Type

from pydantic import BaseModel

from agno.agent import Agent


class AgentTrace(BaseModel):
    """One traced agent invocation."""
    agent_name: str
    phase: str
    timestamp: str
    duration_seconds: float
    # Input
    instructions: List[str]
    prompt: str
    output_schema: Optional[str] = None
    # Output
    raw_response: str
    parsed_output: Optional[str] = None
    output_type: str
    success: bool
    error: Optional[str] = None


class Tracer:
    """Collects and persists agent traces for a pipeline run."""

    def __init__(self, output_dir: Optional[Path] = None, verbose: bool = True):
        self.traces: List[AgentTrace] = []
        self.output_dir = output_dir
        self.verbose = verbose
        self._trace_file: Optional[Path] = None

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            self._trace_file = output_dir / "agent_traces.jsonl"
            # Also a human-readable log
            self._log_file = output_dir / "agent_traces.log"
        else:
            self._log_file = None

    def _append_to_file(self, trace: AgentTrace) -> None:
        """Append trace to JSONL and human-readable log."""
        if self._trace_file:
            with open(self._trace_file, "a", encoding="utf-8") as f:
                f.write(trace.model_dump_json() + "\n")

        if self._log_file:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(self._format_trace_log(trace))

    def _format_trace_log(self, t: AgentTrace) -> str:
        """Format a trace entry for the human-readable log."""
        sep = "=" * 80
        lines = [
            sep,
            f"AGENT: {t.agent_name}",
            f"PHASE: {t.phase}",
            f"TIME:  {t.timestamp}  ({t.duration_seconds:.1f}s)",
            f"STATUS: {'OK' if t.success else 'FAILED'}",
            "",
            "--- INSTRUCTIONS ---",
            "\n".join(t.instructions),
            "",
            "--- INPUT PROMPT ---",
            t.prompt,
            "",
            "--- RAW RESPONSE ---",
            t.raw_response[:5000] + ("..." if len(t.raw_response) > 5000 else ""),
            "",
        ]
        if t.parsed_output:
            lines.extend([
                "--- PARSED OUTPUT ---",
                t.parsed_output[:3000] + ("..." if len(t.parsed_output) > 3000 else ""),
                "",
            ])
        if t.error:
            lines.extend([
                "--- ERROR ---",
                t.error,
                "",
            ])
        lines.append("")
        return "\n".join(lines)

    def _console_log(self, phase: str, agent_name: str, event: str, detail: str = "") -> None:
        """Print a concise console line."""
        if self.verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            prefix = f"  [{ts}] {phase} > {agent_name}"
            try:
                if detail:
                    print(f"{prefix} | {event}: {detail}")
                else:
                    print(f"{prefix} | {event}")
            except UnicodeEncodeError:
                # Fallback for Windows cp1252 console
                safe = f"{prefix} | {event}: {detail}".encode("ascii", "replace").decode()
                print(safe)

    async def traced_arun(
        self,
        agent: Agent,
        prompt: str,
        phase: str,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> Any:
        """
        Run an agent with full tracing.

        Returns the AgentRunResponse (same as agent.arun).
        """
        agent_name = agent.name or "unnamed"
        instructions = agent.instructions if isinstance(agent.instructions, list) else [str(agent.instructions or "")]

        # Log start
        self._console_log(phase, agent_name, "START", f"prompt={len(prompt)} chars")
        if self.verbose:
            # Show a preview of the prompt
            preview = prompt.strip().replace("\n", " ")[:150]
            self._console_log(phase, agent_name, "PROMPT", preview + "...")

        schema_name = output_schema.__name__ if output_schema else None
        start = time.time()
        error_msg = None
        raw_response = ""
        parsed_output = None
        success = False

        try:
            if output_schema:
                response = await agent.arun(prompt, output_schema=output_schema)
            else:
                response = await agent.arun(prompt)

            # Extract raw response
            raw_response = str(response.content) if response.content is not None else ""
            duration = time.time() - start

            # Check if we got the expected schema type
            if output_schema and isinstance(response.content, output_schema):
                parsed_output = response.content.model_dump_json(indent=2)
                success = True
                self._console_log(
                    phase, agent_name, "OK",
                    f"{schema_name} parsed, {len(raw_response)} chars, {duration:.1f}s"
                )
            elif raw_response:
                success = True
                self._console_log(
                    phase, agent_name, "OK (raw)",
                    f"no schema match, {len(raw_response)} chars, {duration:.1f}s"
                )
            else:
                error_msg = "Empty response from agent"
                self._console_log(phase, agent_name, "EMPTY", f"{duration:.1f}s")

        except Exception as exc:
            duration = time.time() - start
            error_msg = str(exc)
            raw_response = f"EXCEPTION: {exc}"
            self._console_log(phase, agent_name, "ERROR", f"{exc}")
            raise
        finally:
            trace = AgentTrace(
                agent_name=agent_name,
                phase=phase,
                timestamp=datetime.now().isoformat(),
                duration_seconds=round(duration, 2),
                instructions=instructions,
                prompt=prompt,
                output_schema=schema_name,
                raw_response=raw_response,
                parsed_output=parsed_output,
                output_type=type(response.content).__name__ if 'response' in dir() else "N/A",
                success=success,
                error=error_msg,
            )
            self.traces.append(trace)
            self._append_to_file(trace)

        return response

    def summary(self) -> str:
        """Print a summary table of all traces."""
        lines = [
            "",
            "=" * 90,
            f"  TRACE SUMMARY — {len(self.traces)} agent calls",
            "=" * 90,
            f"  {'Agent':<30} {'Phase':<15} {'Duration':>8} {'Status':<8} {'Output':<20}",
            "  " + "-" * 85,
        ]
        total_duration = 0.0
        for t in self.traces:
            total_duration += t.duration_seconds
            status = "OK" if t.success else "FAIL"
            output = t.output_type if t.success else (t.error or "")[:20]
            lines.append(
                f"  {t.agent_name:<30} {t.phase:<15} {t.duration_seconds:>7.1f}s {status:<8} {output:<20}"
            )
        lines.append("  " + "-" * 85)
        lines.append(f"  {'TOTAL':<30} {'':<15} {total_duration:>7.1f}s")
        lines.append("=" * 90)
        if self._trace_file:
            lines.append(f"  Full traces: {self._trace_file}")
            lines.append(f"  Readable log: {self._log_file}")
        lines.append("")
        return "\n".join(lines)
