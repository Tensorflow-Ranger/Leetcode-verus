"""Spec loop: write_spec -> check_spec -> critic_spec (-> human_review)."""

from __future__ import annotations

from langgraph.types import interrupt

from .. import guards
from ..config import load
from ..llm import json_section, section
from ..prompts import render
from ..rustlex import LexError, tokenize
from ..state import NodeRun, ProblemState, node, sig_of
from ..template import mutations, spec_literal, spec_only
from ..verus import errors_by_fn


@node("write_spec")
def write_spec(state: ProblemState, run: NodeRun) -> dict:
    sig = sig_of(state)
    rnd = state.get("spec_round", 0) + 1
    system = render("spec_writer", PRE_SIG=sig.pre_sig(), POST_SIG=sig.post_sig())
    user = f"{state['problem_md']}\n\n## Rust signature\n```rust\n{_rust_sig(state)}\n```\n"
    user += "In `pre`/`post`, `Vec<T>` parameters appear as their `Seq` views and the return value as `result`.\n"
    if state.get("spec_feedback"):
        user += f"\n## Your previous spec\n```rust\n{state.get('spec_fns', '')}\n```\n"
        user += f"\n## Problems found with it — fix them\n{state['spec_feedback']}\n"
    text = run.ask("spec_writer", system, user, sample=rnd, required_tags=("spec_fns",))
    spec = section(text, "spec_fns")
    if not spec:
        return {"spec_round": rnd, "spec_fns": "", "spec_feedback": "Your answer had no <spec_fns> section."}
    run.write(f"spec_r{rnd}.rs", spec)
    return {"spec_round": rnd, "spec_fns": spec, "spec_notes": section(text, "notes") or "", "spec_feedback": ""}


def _rust_sig(state: ProblemState) -> str:
    return state["original_fn"].split("{", 1)[0].strip()


@node("check_spec")
def check_spec(state: ProblemState, run: NodeRun) -> dict:
    spec = state.get("spec_fns", "")
    if not spec:
        return {"spec_feedback": state.get("spec_feedback") or "empty spec", "example_results": []}
    errs = guards.check_spec(spec)
    if errs:
        return {"spec_feedback": "\n".join(errs), "example_results": []}
    rnd = state["spec_round"]
    res = run.verus(run.write(f"spec_r{rnd}_typecheck.rs", spec_only(state["uses"], spec)))
    fixed = {}
    for attempt in range(3):  # compile errors are syntax, not meaning: fix them without spending a spec round
        if res.ok:
            break
        user = f"## Spec\n```rust\n{spec}\n```\n\n## Verus errors\n```\n{res.feedback(6000)}\n```\n"
        new = section(run.ask("spec_fixer", render("spec_fixer"), user, sample=attempt, required_tags=("spec_fns",)), "spec_fns")
        if not new or guards.check_spec(new):
            continue
        spec = new
        res = run.verus(run.write(f"spec_r{rnd}_fix{attempt + 1}.rs", spec_only(state["uses"], spec)))
        fixed = {"spec_fns": spec}
        run.extra["syntax_fixes"] = attempt + 1
    if not res.ok:
        return {**fixed, "spec_feedback": "Verus rejected the spec:\n" + res.feedback(6000), "example_results": []}
    if fixed:
        run.write(f"spec_r{rnd}.rs", spec)  # the write-up shows the compiling version of this draft

    results = check_examples(state, run, spec)
    hard = [r for r in results if r["kind"] in ("pre", "post") and r["status"] != "proved"]
    fb = ""
    if fixed:
        fixed["spec_notes"] = state.get("spec_notes", "") + "\n(compile errors fixed by spec_fixer without changing meaning)"
    if hard:
        fb = "The spec does not provably accept these official examples:\n" + "\n".join(_describe(r) for r in hard)
        if not any(r["status"] == "refuted" for r in hard):
            fb += ("\nNone was refuted, so the spec may well be right and just hard to check on concrete data. "
                   "Re-read the problem; if the spec is correct keep its meaning, but prefer a form that unfolds on "
                   "concrete sequences (e.g. a recursive spec fn computing the answer, plus a quantified property), "
                   "so the examples can be checked.")
    return {**fixed, "example_results": results, "spec_feedback": fb}


def _describe(r: dict) -> str:
    what = {"pre": "pre(inputs) should hold", "post": "post(inputs, official output) should hold",
            "neg": "post(inputs, WRONG output) should NOT hold"}[r["kind"]]
    st = ("it is FALSE (Verus evaluated it) — the spec is wrong here" if r["status"] == "refuted"
          else f"not confirmed ({r['status']}): the solver could neither prove nor refute it")
    s = f"- example {r['example'] + 1}: {what}: `{r['assertion']}` — {st}"
    if r.get("note"):
        s += f" (note: {r['note']})"
    return s


def _example_checks(state: ProblemState) -> list[dict]:
    sig = sig_of(state)
    checks = []
    for k, ex in enumerate(state["examples"]):
        args = ", ".join(spec_literal(v, t) for v, (_, t, _) in zip(ex["inputs"], sig.params))
        checks.append({"name": f"ex{k}_pre", "example": k, "kind": "pre", "assertion": f"pre({args})"})
        sep = ", " if args else ""
        checks.append({"name": f"ex{k}_post", "example": k, "kind": "post",
                       "assertion": f"post({args}{sep}{spec_literal(ex['output'], sig.ret)})", "output": ex["output"]})
        for m, wrong in enumerate(mutations(ex["output"], sig.ret)):
            checks.append({"name": f"ex{k}_neg{m}", "example": k, "kind": "neg",
                           "assertion": f"!post({args}{sep}{spec_literal(wrong, sig.ret)})", "output": wrong})
    return checks


def _proof_fns(checks: list[dict], hints: dict[str, str] | None = None, by_compute: bool = False) -> tuple[str, dict]:
    """Render checks as proof fns; return (code, {name: (first_line, last_line)}) relative to the code."""
    lines, ranges = [], {}
    for c in checks:
        start = len(lines) + 1
        lines.append(f"proof fn {c['name']}() {{")
        for h in (hints or {}).get(c["name"], "").splitlines():
            lines.append("    " + h)
        lines.append(f"    assert({c['assertion']}){' by (compute)' if by_compute else ''};")
        lines.append("}")
        ranges[c["name"]] = (start, len(lines))
    return "\n".join(lines), ranges


def _run_checks(state: ProblemState, run: NodeRun, spec: str, checks: list[dict], tag: str,
                hints: dict[str, str] | None = None, by_compute: bool = False) -> dict[str, str]:
    """Verify checks; returns {name: "proved"|"failed"|"refuted"|"timeout"|"crash"}.

    A check is "proved" only if a Verus run containing it succeeded as a whole. Verus may stop
    early (e.g. after a `by (compute)` refutation), so "no error reported" is not evidence: checks
    with attributed errors are removed and the rest are re-run until a run passes.
    """
    if not checks:
        return {}
    code, ranges = _proof_fns(checks, hints, by_compute)
    text = spec_only(state["uses"], spec, code)
    offset = text.splitlines().index(code.splitlines()[0])  # 0-based line of the first check
    res = run.verus(run.write(f"spec_r{state['spec_round']}_{tag}.rs", text), timeout=180)
    if res.ok:
        return {c["name"]: "proved" for c in checks}
    if len(checks) == 1:
        if res.timed_out or res.crashed:
            return {checks[0]["name"]: "timeout" if res.timed_out else "crash"}
        refuted = any("simplifies to false" in e.message for e in res.errors)
        return {checks[0]["name"]: "refuted" if refuted else "failed"}
    shifted = {n: (a + offset, b + offset) for n, (a, b) in ranges.items()}
    failed = errors_by_fn(res, shifted) if not (res.timed_out or res.crashed) else {}
    # `by (compute)` stops at the first refutation, so batching only re-runs the same file over and over:
    # check each assertion in its own file instead.
    if not failed or by_compute:  # can't attribute (timeout, crash, error outside the checks): isolate each check
        out = {}
        for c in checks:
            out.update(_run_checks(state, run, spec, [c], f"{tag}_{c['name']}", hints, by_compute))
        return out
    out = {}
    for c in checks:
        if c["name"] in failed:
            refuted = any("simplifies to false" in e.message for e in failed[c["name"]])
            out[c["name"]] = "refuted" if refuted else "failed"
    rest = [c for c in checks if c["name"] not in failed]
    out.update(_run_checks(state, run, spec, rest, f"{tag}_rest", hints, by_compute))
    return out


def prove_concrete(state: ProblemState, run: NodeRun, spec: str, checks: list[dict], tag: str) -> tuple[dict, dict]:
    """Z3 first, then Verus's interpreter (`by (compute)`), which unfolds recursive spec fns over literals.

    Returns ({name: status}, {name: method}); "refuted" = the interpreter evaluated the assertion to false.
    """
    status = _run_checks(state, run, spec, checks, tag)
    method = {n: "z3" for n, s in status.items() if s == "proved"}
    todo = [c for c in checks if status[c["name"]] != "proved"]
    for n, s in _run_checks(state, run, spec, todo, f"{tag}_compute", by_compute=True).items():
        if s in ("proved", "refuted"):
            status[n], method[n] = s, "compute"
    return status, method


def check_examples(state: ProblemState, run: NodeRun, spec: str) -> list[dict]:
    checks = _example_checks(state)
    status, method = prove_concrete(state, run, spec, checks, "examples")

    # 3rd chance: LLM-written proof hints (cannot weaken anything: `assume`/attributes are rejected)
    notes: dict[str, str] = {}
    tries = load()["budgets"]["example_hint_tries"]
    todo = [c for c in checks if status[c["name"]] not in ("proved", "refuted")][:8]
    for c in todo:
        for t in range(tries):
            hint, note = _ask_hint(state, run, spec, c, t)
            if note:
                notes[c["name"]] = note
                break
            if hint is None:
                continue
            s = _run_checks(state, run, spec, [c], f"examples_hint_{c['name']}_{t}", hints={c["name"]: hint})
            if s[c["name"]] == "proved":
                status[c["name"]], method[c["name"]] = "proved", "hints"
                break

    out = []
    for c in checks:
        r = {k: c[k] for k in ("name", "example", "kind", "assertion")}
        r["status"] = status[c["name"]]
        r["method"] = method.get(c["name"])
        if c["name"] in notes:
            r["note"] = notes[c["name"]]
        out.append(r)
    return out


def _ask_hint(state: ProblemState, run: NodeRun, spec: str, check: dict, attempt: int) -> tuple[str | None, str | None]:
    code, _ = _proof_fns([check])
    user = f"## Spec\n```rust\n{spec}\n```\n\n## Proof fn that failed\n```rust\n{code}\n```\n"
    text = run.ask("example_prover", render("example_prover"), user, sample=attempt)
    false_note = section(text, "false")
    if false_note:
        return None, false_note[:600]
    hint = section(text, "hints")
    if hint is None:
        return None, None
    try:
        toks = tokenize(hint)
    except LexError:
        return None, None
    bad = [t.text for t in toks if t.text in guards.BANNED or t.text in ("#", "fn")]
    return (None, None) if bad else (hint, None)


@node("critic_spec")
def critic_spec(state: ProblemState, run: NodeRun) -> dict:
    ex = state.get("example_results", [])
    summary = "\n".join(
        f"- {r['kind']:4s} example {r['example'] + 1}: `{r['assertion']}` -> {r['status']}"
        + (f" via {r['method']}" if r.get("method") else "") + (f" (prover note: {r['note']})" if r.get("note") else "")
        for r in ex
    ) or "(no machine-checkable examples)"
    user = (f"{state['problem_md']}\n\n## Rust signature\n```rust\n{_rust_sig(state)}\n```\n\n"
            f"## Spec under review\n```rust\n{state['spec_fns']}\n```\n\n## Spec author's notes\n{state.get('spec_notes', '')}\n\n"
            f"## Automated example checks\n{summary}\n")
    verdict = None
    for attempt in range(2):
        verdict = json_section(run.ask("critic", render("spec_critic"), user, sample=attempt, required_tags=("verdict",)),
                               "verdict")
        if verdict and verdict.get("verdict") in ("accept", "revise"):
            break
    verdict = verdict or {"verdict": "revise", "issues": ["critic output unparsable"], "confidence": 0}
    out = {"critic": verdict}
    if verdict["verdict"] == "accept":
        out["spec_hash"] = guards.spec_hash(state["spec_fns"])
    else:
        out["spec_feedback"] = "A reviewer rejected the spec:\n" + "\n".join(f"- {i}" for i in verdict.get("issues", []))
    return out


@node("human_review")
def human_review(state: ProblemState, run: NodeRun) -> dict:
    """Pause the graph (LangGraph interrupt) until a human approves, edits or rejects the spec."""
    decision = interrupt({
        "pid": state["pid"],
        "title": state["question"]["title"],
        "spec_fns": state["spec_fns"],
        "critic": state.get("critic"),
        "examples": state.get("example_results"),
    })
    action = (decision or {}).get("action", "approve")
    if action == "approve":
        return {"review": {"action": "approve"}}
    if action == "edit":
        spec = decision["spec_fns"]
        return {"review": {"action": "edit"}, "spec_fns": spec, "spec_hash": "", "spec_feedback": ""}
    return {"review": {"action": "reject"}, "spec_hash": "",
            "spec_feedback": "A human reviewer rejected the spec: " + decision.get("feedback", "")}


def spec_summary(state: ProblemState) -> dict:
    ex = state.get("example_results", [])
    count = lambda kind: (sum(r["status"] == "proved" for r in ex if r["kind"] == kind), sum(r["kind"] == kind for r in ex))
    return {"pre": count("pre"), "post": count("post"), "neg": count("neg")}

