"""LangGraph state for one problem, plus per-node instrumentation and run artifacts."""

from __future__ import annotations

import functools
import json
import operator
import time
from pathlib import Path
from typing import Annotated, Any, Callable, TypedDict

import openai
from langgraph.errors import GraphBubbleUp

from . import llm, verus
from .config import load
from .template import Signature

FINAL_STATUSES = ("verified", "panic_free", "spec_rejected", "proof_failed", "unsupported", "fetch", "shape", "error",
                  "bug", "spec_suspect")


class ProblemState(TypedDict, total=False):
    # input
    pid: int
    path: str
    review_specs: bool
    # fetch / triage
    status: str
    reason: str
    question: dict  # title, slug, difficulty
    problem_md: str
    examples: list[dict]  # only the ones that parsed and fit the Rust types
    examples_dropped: int
    uses: list[str]
    sig: dict  # Signature fields
    original_fn: str  # the original fn source (signature + body)
    original_body: str
    # spec loop
    spec_round: int
    spec_fns: str
    spec_notes: str
    spec_feedback: str
    example_results: list[dict]
    critic: dict
    spec_hash: str
    review: dict
    # proof loop
    mode: str  # "functional" | "safety"
    proof_round: int
    candidate: dict  # {"lemmas", "body", "analysis"}
    last_file: str
    feedback: str
    last_guard_violation: bool
    best: dict  # {"mode", "lemmas", "body", "errors"}
    last_ok: bool
    final_file: str
    runtime: dict
    # counterexample search
    cex: dict
    cex_runs: int
    safety_proved: bool
    # metrics: every node appends one event (reducer = list concatenation)
    events: Annotated[list[dict], operator.add]


def is_final(status: str | None) -> bool:
    return bool(status) and status.split(":")[0] in FINAL_STATUSES


def sig_of(state: ProblemState) -> Signature:
    s = state["sig"]
    return Signature(s["name"], [tuple(p) for p in s["params"]], s["ret"])


def run_dir(pid: int) -> Path:
    d = load().path("runs") / f"p{pid}"
    d.mkdir(parents=True, exist_ok=True)
    return d


class NodeRun:
    """Handed to each node: records LLM usage and Verus time for the node's event."""

    def __init__(self, name: str, state: ProblemState):
        self.name = name
        self.state = state
        self.llm_calls: list[dict] = []
        self.verus_calls: list[dict] = []
        self.extra: dict = {}  # node-specific fields for the metrics event
        self.dir = run_dir(state["pid"])

    def ask(self, role: str, system: str, user: str, sample: int = 0, required_tags: tuple[str, ...] = ()) -> str:
        r = llm.chat(role, system, user, sample=sample, required_tags=required_tags)
        self.llm_calls.append(r.usage())
        return r.text

    def verus(self, path: Path, **kw) -> verus.VerusResult:
        res = verus.run(path, **kw)
        self.verus_calls.append({"file": path.name, "ok": res.ok, "errors": len(res.errors), "seconds": round(res.seconds, 2),
                                 "timed_out": res.timed_out, "crashed": res.crashed})
        (path.with_suffix(".log")).write_text(res.raw)
        return res

    def write(self, name: str, text: str) -> Path:
        p = self.dir / name
        p.write_text(text)
        return p


def node(name: str) -> Callable:
    """Decorator: wrap `fn(state, run) -> dict` as a LangGraph node that also emits a metrics event."""

    def deco(fn: Callable[[ProblemState, NodeRun], dict]) -> Callable[[ProblemState], dict]:
        @functools.wraps(fn)
        def wrapper(state: ProblemState) -> dict[str, Any]:
            run = NodeRun(name, state)
            t0 = time.time()
            try:
                out = fn(state, run) or {}
            except GraphBubbleUp:  # interrupt() for human review must reach LangGraph
                raise
            except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError):
                raise  # transient: leave the checkpoint before this node so `lcverus run` resumes here
            except openai.APIStatusError as e:
                if e.status_code in (402, 429) or e.status_code >= 500:  # out of credit / throttled / server down
                    raise
                out = {"status": f"error:{name}", "reason": f"{type(e).__name__}: {e}"}
            except Exception as e:  # keep the graph alive; the problem ends with status error
                out = {"status": f"error:{name}", "reason": f"{type(e).__name__}: {e}"}
            ev = {
                "node": name,
                "t": round(t0, 1),
                "seconds": round(time.time() - t0, 2),
                "llm": run.llm_calls,
                "verus": run.verus_calls,
                "spec_round": out.get("spec_round", state.get("spec_round", 0)),
                "proof_round": out.get("proof_round", state.get("proof_round", 0)),
                "mode": out.get("mode", state.get("mode")),
                **run.extra,
            }
            out["events"] = [ev]
            return out

        return wrapper

    return deco


def dump_status(state: ProblemState) -> None:
    d = run_dir(state["pid"])
    keep = {k: v for k, v in state.items() if k not in ("problem_md",)}
    (d / "status.json").write_text(json.dumps(keep, indent=1, default=str))
