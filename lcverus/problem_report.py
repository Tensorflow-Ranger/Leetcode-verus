"""Per-problem write-up: every spec draft, every proof attempt (diff, Verus errors, repair rationale), the outcome.

Written to reports/problems/p<id>.md by `finalize` and by `lcverus report`. The round-by-round data comes from
the run directory (attempt files + Verus logs) and from the LangGraph checkpoint history (each round's candidate,
the repair model's analysis, the spec feedback), so it also works for problems that finished before this existed.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from .config import load
from .state import run_dir

VERDICT = {
    "verified": "**Verified.** Functional spec + panic-freedom + termination proved for the unmodified rustgym code.",
    "panic_free": "**Panic-free only.** The functional proof was not found; no out-of-bounds, overflow, division by zero "
                  "or non-termination was proved for every input satisfying `pre`.",
    "proof_failed": "**Proof not found.** Neither the functional nor the safety proof succeeded within budget, and no "
                    "confirmed counterexample was found. This is inconclusive: it does not mean the code is wrong.",
    "spec_rejected": "**Spec rejected.** No spec survived the example checks and the critic, so no proof was attempted.",
    "bug": "**Bug found.** A concrete input within the constraints breaks the code (see Counterexample).",
    "spec_suspect": "**Spec suspect.** A counterexample showed the spec disagrees with an independent answer; the spec "
                    "needs review before any verdict on the code.",
}


def _history(graph, pid: int) -> list[dict]:
    from .graph import thread_config
    try:
        hist = list(graph.get_state_history(thread_config(pid)))
    except Exception:
        return []
    return [h.values for h in reversed(hist)]  # oldest first


def _errors(log: str, limit: int = 6) -> tuple[str, str]:
    """(one-line summary, trimmed error blocks) from a Verus/checker log."""
    if log.startswith("REJECTED BY THE INTEGRITY CHECKER"):
        return "rejected by the integrity checker (not run through Verus)", log[:1500]
    m = re.search(r"verification results::\s*(\d+) verified,\s*(\d+) errors", log)
    blocks, cur = [], None
    for ln in log.splitlines():
        if re.match(r"^error(\[E\d+\])?:", ln) and "aborting due to" not in ln:
            cur = [ln]
            blocks.append(cur)
        elif re.match(r"^(warning|note: diagnostics)", ln) or ln.startswith("verification results"):
            cur = None
        elif cur is not None and len(cur) < 12:
            cur.append(ln)
    heads = [b[0].removeprefix("error: ") for b in blocks]
    if m and m.group(2) == "0" and not blocks:
        return f"verified ({m.group(1)} items)", ""
    kinds = {}
    for h in heads:
        kinds[h] = kinds.get(h, 0) + 1
    summary = ", ".join(f"{n}× {h}" for h, n in kinds.items()) or "no Verus output (crash or timeout)"
    if m:
        summary = f"{m.group(2)} errors ({m.group(1)} items verified): " + summary
    return summary, "\n\n".join("\n".join(b) for b in blocks[:limit])


def _section(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    s = text.split(start, 1)[1]
    return s.split(end, 1)[0] if end in s else s


def build(pid: int, state: dict, graph=None) -> Path:
    d = run_dir(pid)
    hist = _history(graph, pid) if graph is not None else []
    q = state.get("question") or {}
    status = state.get("status", "?")
    L = [f"# {pid}. {q.get('title', '')}", "", f"Status: `{status}` — " + VERDICT.get(status.split(":")[0], status), ""]
    if state.get("reason") and not status.startswith(("verified", "panic_free")):
        L += [f"Reason: {state['reason']}", ""]

    md = (d / "problem.md").read_text() if (d / "problem.md").exists() else ""
    cons = re.search(r"\*\*Constraints:\*\*(.*?)(\n\*\*|\Z)", md, re.S)
    L += ["## Problem", "", f"LeetCode difficulty: {q.get('difficulty', '?')}. Full statement: `runs/p{pid}/problem.md`.", ""]
    if cons:
        L += ["Constraints:", cons.group(1).strip(), ""]
    if state.get("original_fn"):
        L += ["Original rustgym code (never modified):", "", "```rust", state["original_fn"], "```", ""]

    # ---- spec rounds
    spec_files = sorted(d.glob("spec_r*.rs"), key=lambda p: p.name)
    spec_files = [p for p in spec_files if re.fullmatch(r"spec_r\d+\.rs", p.name)]
    if spec_files:
        L += ["## Spec rounds", ""]
        feedback_by_round = {}
        for v in hist:
            r = v.get("spec_round")
            if r and v.get("example_results") is not None:
                feedback_by_round[r] = (v.get("spec_feedback", ""), v.get("example_results", []), v.get("critic"))
        for p in spec_files:
            rnd = int(re.search(r"\d+", p.name).group())
            fb, ex, crit = feedback_by_round.get(rnd, ("", [], None))
            final = state.get("spec_fns", "").strip() == p.read_text().strip() and state.get("spec_hash")
            L += [f"### Spec draft {rnd}" + (" (frozen)" if final else ""), "", "```rust", p.read_text().strip(), "```", ""]
            if ex:
                L += ["| check | assertion | result |", "|---|---|---|"]
                for r in ex:
                    L.append(f"| {r['kind']} ex{r['example'] + 1} | `{r['assertion'][:90]}` | {r['status']}"
                             f"{' via ' + r['method'] if r.get('method') else ''} |")
                L.append("")
            if fb and not final:
                L += ["Why it was sent back:", "", "> " + fb.replace("\n", "\n> "), ""]
            if crit:
                L += [f"Critic: **{crit.get('verdict')}** (confidence {crit.get('confidence')})"]
                L += [f"- {i}" for i in crit.get("issues") or []]
                L.append("")

    # ---- proof attempts
    attempts = sorted(d.glob("attempt_*.rs"))
    if attempts:
        analysis = {}
        external = {(e.get("mode") or "functional", e["proof_round"]): e["external"]
                    for e in state.get("events", []) if e.get("external")}
        for v in hist:
            c = v.get("candidate") or {}
            if c.get("analysis") and v.get("proof_round"):
                analysis[(v.get("mode", "functional"), v["proof_round"])] = c["analysis"]
        rows = []
        for p in attempts:
            mode, rnd = re.match(r"attempt_(\w+?)_(\d+)\.rs", p.name).groups()
            log = p.with_suffix(".log").read_text() if p.with_suffix(".log").exists() else ""
            rows.append((mode, int(rnd), p, _errors(log)))
        L += ["## Proof attempts", "", "| round | mode | result |", "|---|---|---|"]
        L += [f"| {r} | {m} | {s} |" for m, r, _, (s, _) in rows]
        L.append("")
        prev = None
        for mode, rnd, p, (summary, blocks) in rows:
            text = p.read_text()
            by = external.get((mode, rnd))
            L += [f"### Round {rnd} ({mode}{', written by ' + by if by else ''})", "", f"Result: {summary}", ""]
            if analysis.get((mode, rnd)):
                L += ["What the repair model changed and why:", "", analysis[(mode, rnd)].strip(), ""]
            if prev is None:
                body = _section(text, "// ==== LEMMAS (prover) ====", "} // verus!")
                L += ["Annotated code (lemmas + body):", "", "```rust", body.strip(), "```", ""]
            else:
                diff = list(difflib.unified_diff(prev.splitlines(), text.splitlines(), "previous", "this round", n=2, lineterm=""))
                if diff:
                    shown = diff[:250]
                    L += [f"Change from the previous round ({len(diff)} diff lines{', first 250 shown' if len(diff) > 250 else ''}):",
                          "", "```diff", *shown, "```", ""]
            if blocks:
                L += ["Verus output:", "", "```", blocks[:6000], "```", ""]
            prev = text

    # ---- counterexample
    cex = state.get("cex")
    if cex:
        L += ["## Counterexample search", "", f"Verdict: **{cex.get('verdict')}** — {cex.get('explanation', '')}", ""]
        if cex.get("input") is not None:
            L += [f"- input: `{cex['input']}`", f"- original code returned: `{cex.get('outcome')}`"]
            if cex.get("judge_answer") is not None:
                L.append(f"- independent judge's answer (from the problem text only): `{cex['judge_answer']}`")
            L += [f"- evidence: {', '.join(cex.get('evidence', []))}", ""]
        L += [f"Candidates tried: {cex.get('tried', 0)}; run results: {cex.get('observed', '')}", ""]

    # ---- outcome
    L += ["## Outcome", "", VERDICT.get(status.split(":")[0], status), ""]
    rt = state.get("runtime")
    if rt:
        exm = rt.get("examples", [])
        L += [f"Runtime check of the verified file compiled as plain Rust: {sum(x['match'] for x in exm)}/{len(exm)} LeetCode "
              f"examples match, original rustgym tests: {rt.get('orig_tests')}.", ""]
    if state.get("final_file"):
        L += ["Final verified file (`runs/p%d/final.rs`):" % pid, "", "```rust", state["final_file"].strip(), "```", ""]

    out = load().path("reports") / "problems" / f"p{pid}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L))
    return out
