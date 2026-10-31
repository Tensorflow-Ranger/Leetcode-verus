"""runtime (compile + run examples and the original rustgym tests) and finalize."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from ..rustlex import LexError, find_fns
from ..sources import rustgym
from ..state import NodeRun, ProblemState, dump_status, node, sig_of
from ..template import exec_literal


def _show(v) -> str:
    return json.dumps(v, separators=(", ", ": "))


@node("runtime")
def runtime(state: ProblemState, run: NodeRun) -> dict:
    """Erasure sanity check: the verified file, compiled as ordinary Rust, behaves like the original."""
    sig = sig_of(state)
    calls = []
    for k, ex in enumerate(state["examples"]):
        args = ", ".join(exec_literal(v, t) for v, (_, t, _) in zip(ex["inputs"], sig.params))
        calls.append(f'    println!("EX{k}={{:?}}", Solution::{sig.name}({args}));')
    tests = _original_tests(state)
    out = {"examples": [], "orig_tests": "skipped"}
    for with_tests in ([True, False] if tests else [False]):
        main = ["", "fn main() {", *calls]
        extra = []
        if with_tests:
            for i, body in enumerate(tests):
                extra.append(f"fn __orig_test_{i}() {body}")
                main.append(f"    __orig_test_{i}();")
            main.append('    println!("ORIG_TESTS_OK");')
        main.append("}")
        src = state["final_file"] + "\n".join(main + extra) + "\n"
        path = run.write("runtime.rs", src)
        binary = run.dir / "runtime_bin"
        res = run.verus(path, no_verify=True, compile_to=binary)
        if not res.ok or not binary.exists():
            out["compile_error"] = res.feedback(3000)
            continue
        out.pop("compile_error", None)
        try:
            p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
            stdout, code = p.stdout, p.returncode
        except subprocess.TimeoutExpired:
            stdout, code = "", -1
        got = dict(re.findall(r"^EX(\d+)=(.*)$", stdout, re.M))
        for k, ex in enumerate(state["examples"]):
            g = got.get(str(k))
            out["examples"].append({"example": k, "expected": _show(ex["output"]), "got": g, "match": g == _show(ex["output"])})
        if with_tests:
            out["orig_tests"] = "pass" if "ORIG_TESTS_OK" in stdout and code == 0 else "fail"
        out["exit_code"] = code
        break
    return {"runtime": out}


def _original_tests(state: ProblemState) -> list[str]:
    src = rustgym.parse_file(Path(state["path"]))
    if not src.tests or re.search(r"rustgym_util|[a-z_]+!\s*\[\s*\[|assert_approx_eq|vec_vec|vec_string", src.tests):
        return []
    try:
        return [f.body for f in find_fns(src.tests)]
    except LexError:
        return []


@node("finalize")
def finalize(state: ProblemState, run: NodeRun) -> dict:
    status = state.get("status") or "running"
    if status == "running":
        if not state.get("spec_hash"):
            status = "spec_rejected"
        else:
            status = "proof_failed:guard_violation" if state.get("last_guard_violation") else "proof_failed"
    if state.get("spec_fns"):
        run.write("spec.rs", state["spec_fns"])
    final = {**state, "status": status}
    dump_status(final)
    try:
        from ..graph import compile_graph
        from ..problem_report import build as write_problem_report
        write_problem_report(state["pid"], final, compile_graph())
    except Exception:  # the write-up is a convenience; never fail the run over it
        pass
    return {"status": status}
