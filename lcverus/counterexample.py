"""Counterexample search: run the ORIGINAL rustgym code on candidate inputs.

Nothing here decides that the code is wrong. It only produces observations
(input -> output | panic | timeout). Whether an observation is a real bug is
decided in nodes/bug.py, and only from facts Verus proves about the frozen spec
(`pre(X)`, `!post(X, Y)`) plus an independent judge's answer that Verus checks
against the spec.
"""

from __future__ import annotations

import itertools
import json
import os
import random
import re
import subprocess
from pathlib import Path

from .template import SCALARS, exec_literal, fits

TOOLCHAIN = "1.99.1-x86_64-unknown-linux-gnu"

INT_EDGES = [0, 1, 2, -1, -2, 3, 4, 5, 7, 8, 9, 10, 16, 31, 32, 100, 1000, 10**4, 10**5, 10**9, -10**9,
             2**31 - 1, 2**31 - 2, -(2**31), -(2**31) + 1, 2**30, 2**16]
MAX_LEN = 40  # keep literals small enough for Verus


def _scalar_values(t: str, seen: list) -> list:
    vals = list(INT_EDGES) + [v + d for v in seen for d in (-1, 0, 1)]
    return [v for v in dict.fromkeys(vals) if fits(v, t)]


def _vec_values(t: str, seen: list, rng: random.Random) -> list:
    inner = t[4:-1]
    if inner == "bool":
        base = [[], [True], [False], [True, True], [True, False], [False] * 5]
        base += [list(s) for s in seen] + [[not b for b in s] for s in seen]
    elif inner.startswith("Vec<"):
        base = [[], [[]], [[0]], [[1]], [[1, 2], [3, 4]], [[0, 0], [0, 0]], [[1]] * 3]
        base += [s for s in seen] + [s[:-1] for s in seen if s] + [[r[::-1] for r in s] for s in seen]
    else:
        mx, mn = (2**31 - 1, -(2**31)) if inner == "i32" else (2**63 - 1, -(2**63))
        base = [[], [0], [1], [-1], [2], [mx], [mn], [mx, mx], [mn, mn], [mx, mn], [0, 0], [1, 1], [1, 0], [0, 1],
                [1, 2, 3], [3, 2, 1], [5] * 5, list(range(1, 11)), list(range(10, 0, -1)), [mx, 1], [mn, -1]]
        for big in (10**4, 10**5, 10**9, -10**9, 2**30, mx, mn):  # repeated extremes: overflow in sums/products
            base += [[big] * k for k in (2, 3, 10, MAX_LEN)]
        for s in seen:
            base += [s, s[:-1], s[1:], s[::-1], sorted(s), sorted(s, reverse=True), s + s,
                     [x + 1 for x in s], [x - 1 for x in s], s + [max(s, default=0) + 1], [s[0]] if s else []]
            if s:
                base.append([rng.choice(s) for _ in range(min(MAX_LEN, 2 * len(s) + 3))])
    out = []
    for v in base:
        v = v[:MAX_LEN]
        if fits(v, t) and v not in out:
            out.append(v)
    return out


def candidates(sig, examples: list[dict], extra: list[list] | None = None, limit: int = 80, seed: int = 0) -> list[list]:
    """Boundary/edge-case inputs (as JSON values per param), examples first-varied one param at a time."""
    rng = random.Random(seed)
    types = [t for _, t, _ in sig.params]
    seen = [[ex["inputs"][k] for ex in examples] for k in range(len(types))]
    per_param = []
    for k, t in enumerate(types):
        vals = _scalar_values(t, seen[k]) if t in SCALARS else _vec_values(t, seen[k], rng)
        per_param.append(vals)
    bases = [ex["inputs"] for ex in examples] or [[vals[0] for vals in per_param]]
    out: list[list] = []

    def add(c):
        if all(fits(v, t) for v, t in zip(c, types)) and c not in out:
            out.append(c)

    for c in extra or []:
        if isinstance(c, list) and len(c) == len(types):
            add(c)
    for base in bases:  # vary one parameter at a time around each example
        for k, vals in enumerate(per_param):
            for v in vals:
                add(base[:k] + [v] + base[k + 1 :])
    for c in itertools.islice(itertools.product(*per_param), 400):  # a few joint combinations
        add(list(c))
    head, tail = out[: limit // 2], out[limit // 2 :]
    rng.shuffle(tail)
    return (head + tail)[:limit]


def _harness(solution: str, sig, cases: list[list]) -> str:
    arms = []
    for k, c in enumerate(cases):
        args = ", ".join(exec_literal(v, t) for v, (_, t, _) in zip(c, sig.params))
        arms.append(f'        {k} => format!("{{:?}}", Solution::{sig.name}({args})),')
    return f"""#![allow(dead_code, unused_imports, unused_variables, unused_mut)]
{solution}

fn main() {{
    std::panic::set_hook(Box::new(|info| {{ eprintln!("PANIC {{}}", info); }}));
    let k: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    let out = match k {{
{chr(10).join(arms)}
        _ => unreachable!(),
    }};
    println!("RESULT {{}}", out);
}}
"""


def run_original(solution: str, sig, cases: list[list], workdir: Path, timeout_s: float = 5.0) -> list[dict]:
    """Compile the original code with overflow checks and run each case in its own process."""
    src = workdir / "cex_harness.rs"
    binary = workdir / "cex_harness"
    src.write_text(_harness(solution, sig, cases))
    cargo = Path.home() / ".cargo" / "bin"
    env = {**os.environ, "PATH": f"{cargo}:{os.environ.get('PATH', '')}"}
    p = subprocess.run([str(cargo / "rustup"), "run", TOOLCHAIN, "rustc", "--edition", "2018", "-C", "overflow-checks=on",
                        "-C", "debug-assertions=on", "-C", "opt-level=1", str(src), "-o", str(binary)],
                       capture_output=True, text=True, env=env, timeout=300)
    if p.returncode != 0:
        raise RuntimeError("original code does not compile standalone:\n" + p.stderr[-2000:])
    results = []
    for k, c in enumerate(cases):
        try:
            r = subprocess.run([str(binary), str(k)], capture_output=True, text=True, timeout=timeout_s)
            m = re.search(r"^RESULT (.*)$", r.stdout, re.M)
            if r.returncode == 0 and m:
                try:
                    out = json.loads(m.group(1))
                except ValueError:
                    out = m.group(1)
                results.append({"case": k, "input": c, "outcome": "ok", "output": out})
            else:
                # the hook prints "PANIC panicked at file:line:col:\n<message>"; keep the message, not the harness path
                pm = re.search(r"PANIC panicked at [^\n]*:\n?(.*)", r.stderr, re.S)
                msg = (pm.group(1) if pm else r.stderr[-300:]).strip().splitlines()
                results.append({"case": k, "input": c, "outcome": "panic", "message": (msg[0] if msg else "panic")[:300]})
        except subprocess.TimeoutExpired:
            results.append({"case": k, "input": c, "outcome": "timeout"})
    return results
