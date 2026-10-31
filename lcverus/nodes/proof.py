"""Proof loop: prove -> verify -> (repair -> verify)* -> safety_fallback -> verify ..."""

from __future__ import annotations

from .. import guards
from ..config import load
from ..llm import json_section, section
from ..prompts import render
from ..state import NodeRun, ProblemState, node, sig_of
from ..template import assemble, numbered

SAFETY_NOTE = """
5. MODE: panic-freedom only. The functional postcondition was dropped for this attempt; the goal is to prove
   that the code never panics (no out-of-bounds index, no overflow/underflow, no division by zero) and always
   terminates, assuming only `pre`. Invariants only need to carry bounds, not functional facts."""


def _context(state: ProblemState) -> str:
    sig = sig_of(state)
    mode = state.get("mode", "functional")
    header = sig.exec_header(mode)
    return (
        f"{state['problem_md']}\n\n"
        f"## Frozen spec (cannot be changed)\n```rust\n{state['spec_fns']}\n```\n\n"
        f"## Signature the orchestrator will emit\n```rust\n{header}\n```\n\n"
        f"## ORIGINAL rustgym code (executable statements must stay exactly this)\n```rust\n{state['original_fn']}\n```\n"
    )


def _parse(text: str) -> dict:
    claim = json_section(text, "suspected_bug")
    return {"lemmas": section(text, "lemmas") or "", "body": section(text, "body") or "", "analysis": section(text, "analysis") or "",
            "suspected_bug": claim if isinstance(claim, dict) else None}


def _mode_note(state: ProblemState) -> str:
    return SAFETY_NOTE if state.get("mode") == "safety" else ""


@node("prove")
def prove(state: ProblemState, run: NodeRun) -> dict:
    text = run.ask("prover", render("prover", MODE_NOTE=_mode_note(state)), _context(state), required_tags=("body",))
    return {"candidate": _parse(text), "proof_round": state.get("proof_round", 0) + 1}


@node("repair")
def repair(state: ProblemState, run: NodeRun) -> dict:
    hist = [e for e in state.get("events", []) if e["node"] == "verify" and e.get("mode") == state.get("mode")]
    trend = ", ".join(str(e.get("result", {}).get("errors", "?")) for e in hist[-6:])
    best = state.get("best")
    base_file, base_fb, base_round = state["last_file"], state["feedback"], state["proof_round"]
    note = ""
    if best and best.get("mode") == state.get("mode") and best.get("round") not in (None, state["proof_round"]):
        # the last round regressed: build on the best attempt instead, but say what went wrong
        note = (f"\nNote: round {state['proof_round']} was worse than round {best['round']}; it failed with:\n"
                f"```\n{state['feedback'][:3000]}\n```\nStart again from the best attempt below.\n")
        base_file, base_fb, base_round = best["file"], best["feedback"], best["round"]
    user = (
        _context(state)
        + note
        + f"\n## Attempt to fix (round {base_round}, full file as verified)\n```rust\n{numbered(base_file)}\n```\n"
        + f"\n## Verus / checker output for it\n```\n{base_fb}\n```\n"
        + (f"\nError counts in previous rounds: {trend}\n" if trend else "")
    )
    text = run.ask("repair", render("repair", MODE_NOTE=_mode_note(state)), user, sample=state["proof_round"],
                   required_tags=("body|suspected_bug",))
    cand = _parse(text)
    if cand["suspected_bug"]:
        run.extra["suspected_bug"] = cand["suspected_bug"]
        return {"candidate": cand}  # not a proof round: the claim goes to find_counterexample
    return {"candidate": cand, "proof_round": state["proof_round"] + 1}


@node("verify")
def verify(state: ProblemState, run: NodeRun) -> dict:
    cand = state["candidate"]
    mode = state.get("mode", "functional")
    sig = sig_of(state)
    text = assemble(sig, state["uses"], state["spec_fns"], cand["lemmas"], cand["body"] or "{}", mode)
    name = f"attempt_{mode}_{state['proof_round']:02d}.rs"
    path = run.write(name, text)

    # The spec in the file is the frozen one by construction; re-check the hash anyway.
    violations = [] if guards.spec_hash(state["spec_fns"]) == state.get("spec_hash") else ["spec hash changed"]
    if not cand["body"]:
        violations.append("answer had no <body> section")
    violations += guards.check_candidate(cand["lemmas"], cand["body"], state["original_body"])
    if violations:
        fb = "REJECTED BY THE INTEGRITY CHECKER (not run through Verus):\n" + "\n".join(violations)
        (path.with_suffix(".log")).write_text(fb)
        run.extra["result"] = {"ok": False, "errors": None, "guard": True}
        return {"last_file": text, "feedback": fb, "last_guard_violation": True, "last_ok": False}

    res = run.verus(path)
    out = {"last_file": text, "feedback": res.feedback(), "last_guard_violation": False, "last_ok": res.ok}
    errors = 0 if res.ok else max(len(res.errors), 1)
    # A file that doesn't type-check proves nothing yet: rank it below any file with only proof errors.
    # Verus prints "verification results::" only once the file compiled, so its absence covers every compile-time
    # error (syntax, types, triggers, undefined names), not just the ones with an E-code.
    compiled = res.ok or "verification results::" in res.raw
    score = errors + (0 if compiled else 1000)
    best = state.get("best")
    better = best is None or best["mode"] != mode or score < best.get("score", best["errors"])
    if better:
        out["best"] = {"mode": mode, "lemmas": cand["lemmas"], "body": cand["body"], "errors": errors, "score": score,
                       "file": text, "feedback": out["feedback"], "round": state["proof_round"]}
    if res.ok:
        if str(state.get("status", "")).startswith("bug:"):
            out["safety_proved"] = True  # a confirmed wrong-answer bug stays the verdict; panic-freedom is extra
        else:
            out["status"] = "verified" if mode == "functional" else "panic_free"
        out["final_file"] = text
        run.write("final.rs", text)
    run.extra["result"] = {"ok": res.ok, "errors": errors, "kinds": sorted({e.kind for e in res.errors}),
                      "timed_out": res.timed_out}
    return out


@node("safety_fallback")
def safety_fallback(state: ProblemState, run: NodeRun) -> dict:
    """Functional proof failed within budget: retry proving panic-freedom + termination only."""
    best = state.get("best") or state["candidate"]
    return {"mode": "safety", "proof_round": 1, "candidate": {"lemmas": best["lemmas"], "body": best["body"], "analysis": ""}}


def route_after_verify(state: ProblemState) -> str:
    from .bug import can_search
    if state.get("last_ok"):
        return "finalize" if str(state.get("status", "")).startswith("bug:") else "runtime"
    b = load()["budgets"]
    functional = state.get("mode", "functional") == "functional"
    budget = b["proof_rounds"] if functional else b["safety_rounds"]
    if state["proof_round"] < budget:
        return "repair"
    if functional and can_search(state):
        return "find_counterexample"  # before giving up: is the code (or the spec) actually wrong?
    if functional and b["safety_rounds"] > 0:
        return "safety_fallback"
    return "finalize"


def route_after_repair(state: ProblemState) -> str:
    from .bug import can_search
    if (state.get("candidate") or {}).get("suspected_bug"):
        return "find_counterexample" if can_search(state) else "verify"
    return "verify"
