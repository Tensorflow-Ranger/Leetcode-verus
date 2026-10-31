"""find_counterexample: is the code wrong, the spec wrong, or just the proof hard?

Runs when the functional proof budget is spent, or when the repair model claims a bug (<suspected_bug>).
The original rustgym code is executed on candidate inputs; a claim is only made from facts Verus proves:

  input X valid          Verus proves pre(X)               (and the judge agrees X meets the constraints)
  code panics on X       observed with overflow checks on  -> bug:panic
  code's answer Y wrong  Verus proves !post(X, Y)
  judge's answer E right Verus proves post(X, E), E != Y   -> bug:wrong_answer

Disagreements are blamed on the spec, not the code: the judge says X violates a constraint (pre too weak), or the
spec rejects the judge's answer too (post wrong) -> back to the spec loop with X as feedback (the code's output is
withheld from the spec writer). Nothing confirmed -> the code is not blamed and the proof search goes on.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import load
from ..counterexample import candidates, run_original
from ..llm import json_section
from ..prompts import render
from ..sources import rustgym
from ..state import NodeRun, ProblemState, node, sig_of
from ..template import fits, spec_literal
from .spec import _run_checks, prove_concrete

MAX_RUNS = 2  # counterexample searches per problem (claims + the end-of-budget search)


def _args(x: list, sig) -> str:
    return ", ".join(spec_literal(v, t) for v, (_, t, _) in zip(x, sig.params))


def _post(x: list, y, sig, negate: bool = False) -> str:
    sep = ", " if sig.params else ""
    return f"{'!' if negate else ''}post({_args(x, sig)}{sep}{spec_literal(y, sig.ret)})"


@node("find_counterexample")
def find_counterexample(state: ProblemState, run: NodeRun) -> dict:
    sig = sig_of(state)
    claim = (state.get("candidate") or {}).get("suspected_bug")
    trigger = "claim" if claim else "budget"
    claimed = [x for x in (claim or {}).get("inputs", []) if isinstance(x, list)]
    src = rustgym.parse_file(Path(state["path"]))
    cands = candidates(sig, state["examples"], extra=claimed, limit=60 if trigger == "budget" else 30, seed=state["pid"])
    observed = run_original(src.solution, sig, cands, run.dir)
    counts = {k: sum(o["outcome"] == k for o in observed) for k in ("ok", "panic", "timeout")}

    # What does Verus say about each observation under the frozen spec?
    checks = []
    for o in observed:
        x = o["input"]
        checks.append({"name": f"c{o['case']}_pre", "example": o["case"], "kind": "pre", "assertion": f"pre({_args(x, sig)})"})
        if o["outcome"] == "ok" and fits(o["output"], sig.ret):
            checks.append({"name": f"c{o['case']}_wrong", "example": o["case"], "kind": "neg",
                           "assertion": _post(x, o["output"], sig, negate=True)})
    # Z3 on everything, then the (slow, one-file-per-check) interpreter only where it can change the verdict:
    # "is the code's answer wrong?", and "is this input valid?" for observations that look like failures.
    st = _run_checks(state, run, state["spec_fns"], checks, "cex")
    by_name = {c["name"]: c for c in checks}
    todo = [c for c in checks if c["kind"] == "neg" and st[c["name"]] != "proved"]
    st.update({n: v for n, v in _run_checks(state, run, state["spec_fns"], todo, "cex_compute", by_compute=True).items()
               if v == "proved"})
    suspicious = {o["case"] for o in observed if o["outcome"] != "ok" or st.get(f"c{o['case']}_wrong") == "proved"}
    todo = [by_name[f"c{k}_pre"] for k in suspicious if st[f"c{k}_pre"] != "proved"]
    st.update({n: v for n, v in _run_checks(state, run, state["spec_fns"], todo, "cex_pre_compute", by_compute=True).items()
               if v == "proved"})
    valid = {o["case"] for o in observed if st.get(f"c{o['case']}_pre") == "proved"}
    panics = [o for o in observed if o["case"] in valid and o["outcome"] == "panic"]
    wrong = [o for o in observed if o["case"] in valid and st.get(f"c{o['case']}_wrong") == "proved"]
    hangs = [o for o in observed if o["case"] in valid and o["outcome"] == "timeout"]
    base = {"trigger": trigger, "tried": len(observed), "observed": counts, "valid_inputs": len(valid)}
    runs = state.get("cex_runs", 0) + 1

    size = lambda o: len(json.dumps(o["input"]))
    for o in sorted(panics, key=size) + sorted(wrong, key=size):  # smallest confirmed failure first
        verdict = _judge(state, run, o["input"])
        if verdict is None:
            continue
        ev = ["Verus proves pre(X)"]
        if not verdict.get("valid", True):
            return _spec_suspect(state, base, runs, o, verdict,
                                 f"`pre` admits {o['input']}, but the problem's constraints exclude it "
                                 f"({verdict.get('violated_constraint')}).")
        ev.append("judge: X satisfies the constraints")
        if o["outcome"] == "panic":
            cex = {**base, "verdict": "bug:panic", "input": o["input"], "outcome": f"panic: {o.get('message', '')[:200]}",
                   "judge_answer": verdict.get("answer"), "evidence": ev + ["the original code panics on X (overflow checks on)"],
                   "explanation": "a valid input makes the original code panic."}
            return {"cex": cex, "cex_runs": runs, "status": "bug:panic", "reason": cex["explanation"]}
        e = verdict.get("answer")
        if e is None or not fits(e, sig.ret) or e == o["output"]:
            return _spec_suspect(state, base, runs, o, verdict,
                                 f"on input {o['input']} the spec rejects an output the independent judge considers correct.")
        ok, _ = prove_concrete(state, run, state["spec_fns"],
                               [{"name": "judge_post", "example": 0, "kind": "post", "assertion": _post(o["input"], e, sig)}],
                               f"cex_judge_{o['case']}")
        if ok.get("judge_post") != "proved":
            return _spec_suspect(state, base, runs, o, verdict,
                                 f"on input {o['input']} the spec does not accept the judge's answer {e}.")
        cex = {**base, "verdict": "bug:wrong_answer", "input": o["input"], "outcome": o["output"], "judge_answer": e,
               "evidence": ev + [f"Verus proves !post(X, {o['output']}) — the code's answer violates the spec",
                                 f"Verus proves post(X, {e}) — the judge's answer satisfies it"],
               "explanation": f"on a valid input the original code returns {o['output']}, the correct answer is {e}."}
        return {"cex": cex, "cex_runs": runs, "status": "bug:wrong_answer", "reason": cex["explanation"]}

    # Nothing confirmed: the code is not blamed.
    note = f"{len(observed)} inputs run ({counts}); {len(valid)} proven valid; no confirmed failure."
    if hangs:
        note += f" {len(hangs)} valid inputs exceeded the 5 s time limit (not counted as a bug: no proof of a hang)."
    cex = {**base, "verdict": "none", "explanation": note, "hangs": [h["input"] for h in hangs[:3]]}
    out = {"cex": cex, "cex_runs": runs}
    if trigger == "claim":
        facts = []
        for x in claimed[:5]:
            o = next((o for o in observed if o["input"] == x), None)
            if o is None:
                facts.append(f"- {x}: not a well-typed input for this signature")
                continue
            v = "valid (pre holds)" if o["case"] in valid else "NOT shown to satisfy pre"
            res = o.get("output", o["outcome"])
            ok = st.get(f"c{o['case']}_wrong") != "proved"
            facts.append(f"- {x}: {v}; original code returns {res}; " + ("spec accepts it" if ok else "spec rejects it"))
        out["feedback"] = ("Your <suspected_bug> was checked by running the original code and asking Verus:\n"
                           + "\n".join(facts) + f"\nSearch over {len(observed)} inputs found no confirmed failure. "
                           "Treat the code as correct and continue the proof.\n\n" + state.get("feedback", ""))
        out["candidate"] = {**(state.get("best") or state["candidate"]), "suspected_bug": None}
    return out


def _judge(state: ProblemState, run: NodeRun, x: list) -> dict | None:
    names = [n for n, _, _ in sig_of(state).params]
    shown = ", ".join(f"{n} = {json.dumps(v)}" for n, v in zip(names, x))
    user = f"{state['problem_md']}\n\n## Input to judge\n{shown}\n"
    for attempt in range(2):
        v = json_section(run.ask("judge", render("judge"), user, sample=attempt, required_tags=("verdict",)), "verdict")
        if isinstance(v, dict) and "valid" in v:
            return v
    return None


def _spec_suspect(state: ProblemState, base: dict, runs: int, o: dict, verdict: dict, why: str) -> dict:
    cex = {**base, "verdict": "spec_suspect", "input": o["input"], "outcome": o.get("output", o["outcome"]),
           "judge_answer": verdict.get("answer"), "evidence": ["Verus proves pre(X)", f"judge: {verdict.get('reasoning', '')[:300]}"],
           "explanation": why}
    out = {"cex": cex, "cex_runs": runs}
    if state.get("spec_round", 0) < load()["budgets"]["spec_rounds"]:
        # Back to the spec loop. The code's output is withheld so the spec cannot be bent towards the code.
        out.update({"spec_hash": "", "proof_round": 0, "mode": "functional", "best": None, "status": "running",
                    "spec_feedback": f"A concrete input exposed a problem with the spec: {why} The judge's reasoning: "
                                     f"{verdict.get('reasoning', '')}"})
    else:
        out.update({"status": "spec_suspect", "reason": why})
    return out


def route_after_cex(s: ProblemState) -> str:
    v = (s.get("cex") or {}).get("verdict", "none")
    if v == "bug:panic":
        return "finalize"
    if v == "bug:wrong_answer":
        return "safety_fallback"  # still worth knowing: does it at least never panic?
    if v == "spec_suspect":
        return "write_spec" if s.get("status") == "running" else "finalize"
    if s["cex"].get("trigger") == "claim":
        return "repair"
    return "safety_fallback"


def can_search(s: ProblemState) -> bool:
    return s.get("cex_runs", 0) < MAX_RUNS
