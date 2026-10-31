"""fetch + triage: deterministic, no LLM."""

from __future__ import annotations

import re
from pathlib import Path

from .. import rustlex
from ..config import load
from ..sources import leetcode, rustgym
from ..state import NodeRun, ProblemState, node
from ..template import Signature, fits


@node("fetch")
def fetch(state: ProblemState, run: NodeRun) -> dict:
    q = leetcode.fetch(state["pid"])
    if not q:
        return {"status": "fetch:not_found", "reason": "no LeetCode problem with this frontend id"}
    if not q.get("content"):
        return {"status": "fetch:premium", "reason": "statement is LeetCode Premium only"}
    md = leetcode.to_markdown(q)
    run.write("problem.md", md)
    return {
        "question": {"title": q["title"], "slug": q["titleSlug"], "difficulty": q["difficulty"]},
        "problem_md": md,
        "examples": leetcode.parse_examples(q),
        "status": "running",
    }


@node("triage")
def triage(state: ProblemState, run: NodeRun) -> dict:
    return analyze(Path(state["path"]), state["examples"], run.verus, run.write)


def _continue_in_for(body: str) -> bool:
    """True if a `continue` targets a `for` loop (its innermost enclosing loop is a `for`)."""
    stack, pending = [], None
    for t in rustlex.tokenize(body):
        if t.text in ("for", "while", "loop"):
            pending = t.text
        elif t.text == "{":
            stack.append(pending)
            pending = None
        elif t.text == "}":
            if stack:
                stack.pop()
        elif t.text == "continue":
            loops = [k for k in stack if k]
            if loops and loops[-1] == "for":
                return True
    return False


def analyze(path: Path, examples: list[dict], verus_fn, write_fn) -> dict:
    """Shape filter + `verus --no-verify` on the untouched original. Also used by pilot selection."""
    src = rustgym.parse_file(path)
    issue = rustgym.shape_issue(src, set(load()["pilot"]["types"]))
    if issue:
        return {"status": issue, "reason": issue}
    f = src.fns[0]
    sig = Signature(f["name"], [tuple(p) for p in f["params"]], f["ret"])

    usable = []
    for ex in examples:
        ok = ex["inputs"] is not None and ex["output"] is not None
        ok = ok and len(ex["inputs"]) == len(sig.params)
        ok = ok and all(fits(v, t) for v, (_, t, _) in zip(ex["inputs"], sig.params)) and fits(ex["output"], sig.ret)
        if ok:
            usable.append(ex)

    # Does Verus accept the original code (modulo proofs) at all? `--no-verify` = parse + type/mode check only.
    wrapped = "\n".join(["use vstd::prelude::*;", "verus! {", *src.uses, "struct Solution;", "impl Solution {",
                         f["sig"] + " " + f["body"], "}", "} // verus!", ""])
    res = verus_fn(write_fn("triage.rs", wrapped), no_verify=True)
    base = {
        "sig": {"name": sig.name, "params": sig.params, "ret": sig.ret},
        "uses": src.uses,
        "original_fn": f["sig"] + " " + f["body"],
        "original_body": f["body"],
        "examples": usable,
        "examples_dropped": len(examples) - len(usable),
    }
    if not res.ok:
        msg = res.errors[0].message if res.errors else res.raw[-500:]
        return {**base, "status": f"unsupported:{_feature(msg)}", "reason": msg}
    if _continue_in_for(f["body"]):  # rejected by Verus only at verification time, which --no-verify skips
        return {**base, "status": "unsupported:continue_in_for", "reason": "Verus does not support `continue` in `for` loops"}
    return {**base, "status": "running", "spec_round": 0, "proof_round": 0, "mode": "functional"}


def _feature(msg: str) -> str:
    m = re.search(r"`([^`]+)` is not supported", msg)
    if m:
        name = m.group(1)
        return re.sub(r"^(core|alloc|std)::", "", re.sub(r"\[[0-9a-f]+\]", "", name))[:60]
    return re.sub(r"[^a-z0-9_]+", "_", msg.lower())[:60].strip("_")
