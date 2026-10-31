"""Assemble Verus files from frozen pieces + LLM pieces, and render example literals.

Layout of every generated proof file (the orchestrator owns everything except
the two LLM-written regions LEMMAS and BODY):

    use vstd::prelude::*;
    verus! {
    <original `use` lines>
    // ==== SPEC (frozen) ====
    spec fn pre(..) -> bool { .. }
    spec fn post(.., result: ..) -> bool { .. }
    // ==== LEMMAS (prover) ====
    ..
    struct Solution;
    impl Solution {
        fn name(params) -> (result: Ret)
            requires pre(views),
            ensures post(views, result_view),
        BODY
    }
    }
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

SCALARS = {"i32", "i64", "u32", "u64", "usize", "bool"}


def view_type(t: str) -> str:
    if t in SCALARS:
        return t
    m = re.fullmatch(r"Vec<(.+)>", t)
    if m:
        return f"Seq<{view_type(m.group(1))}>"
    raise ValueError(f"unsupported type {t}")


def view_expr(name: str, t: str) -> str:
    if t in SCALARS:
        return name
    if re.fullmatch(r"Vec<[a-z0-9]+>", t):
        return f"{name}@"
    return f"{name}.deep_view()"


@dataclass
class Signature:
    name: str
    params: list[tuple[str, str, bool]]
    ret: str | None

    def spec_params(self) -> str:
        return ", ".join(f"{n}: {view_type(t)}" for n, t, _ in self.params)

    def pre_sig(self) -> str:
        return f"spec fn pre({self.spec_params()}) -> bool"

    def post_sig(self) -> str:
        res = f", result: {view_type(self.ret)}" if self.ret else ""
        return f"spec fn post({self.spec_params()}{res}) -> bool"

    def views(self) -> str:
        return ", ".join(view_expr(n, t) for n, t, _ in self.params)

    def exec_header(self, mode: str) -> str:
        ps = ", ".join(f"{'mut ' if m else ''}{n}: {t}" for n, t, m in self.params)
        ret = f" -> (result: {self.ret})" if self.ret else ""
        lines = [
            "    #[verifier::loop_isolation(false)]",
            f"    fn {self.name}({ps}){ret}",
            f"        requires pre({self.views()}),",
        ]
        if mode == "functional":
            res = ", " + view_expr("result", self.ret) if self.ret else ""
            lines.append(f"        ensures post({self.views()}{res}),")
        return "\n".join(lines)


SPEC_MARK = "// ==== SPEC (frozen) ===="
LEMMA_MARK = "// ==== LEMMAS (prover) ===="
BODY_MARK = "// ==== BODY (prover) ===="


def assemble(sig: Signature, uses: list[str], spec_fns: str, lemmas: str, body: str, mode: str = "functional") -> str:
    parts = [
        "use vstd::prelude::*;",
        "verus! {",
        *uses,
        SPEC_MARK,
        spec_fns.strip(),
        LEMMA_MARK,
        lemmas.strip(),
        "struct Solution;",
        "impl Solution {",
        sig.exec_header(mode),
        BODY_MARK,
        indent(body.strip(), 4),
        "}",
        "} // verus!",
        "",
    ]
    return "\n".join(parts)


def spec_only(uses: list[str], spec_fns: str, extra: str = "") -> str:
    return "\n".join(["use vstd::prelude::*;", "verus! {", *uses, SPEC_MARK, spec_fns.strip(), extra, "} // verus!", ""])


def indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + ln if ln.strip() else ln for ln in s.splitlines())


def numbered(s: str) -> str:
    return "\n".join(f"{i:4d} | {ln}" for i, ln in enumerate(s.splitlines(), 1))


# ---------- literals ----------

def spec_literal(v, t: str) -> str:
    """A spec-mode literal (Seq for vectors) of LeetCode JSON value v at Rust type t."""
    if t == "bool":
        return "true" if v else "false"
    if t in SCALARS:
        return f"{int(v)}{t}" if int(v) >= 0 else f"({int(v)}{t})"
    m = re.fullmatch(r"Vec<(.+)>", t)
    if m:
        inner = m.group(1)
        if not v:
            return f"Seq::<{view_type(inner)}>::empty()"
        return "seq![" + ", ".join(spec_literal(x, inner) for x in v) + "]"
    raise ValueError(t)


def exec_literal(v, t: str) -> str:
    if t == "bool":
        return "true" if v else "false"
    if t in SCALARS:
        return f"{int(v)}{t}" if int(v) >= 0 else f"({int(v)}{t})"
    m = re.fullmatch(r"Vec<(.+)>", t)
    if m:
        inner = m.group(1)
        if not v:
            return f"Vec::<{inner}>::new()"
        return "vec![" + ", ".join(exec_literal(x, inner) for x in v) + "]"
    raise ValueError(t)


def fits(v, t: str) -> bool:
    lim = {"i32": (-(2**31), 2**31 - 1), "i64": (-(2**63), 2**63 - 1), "u32": (0, 2**32 - 1), "u64": (0, 2**64 - 1), "usize": (0, 2**64 - 1)}
    if t == "bool":
        return isinstance(v, bool)
    if t in lim:
        return isinstance(v, int) and not isinstance(v, bool) and lim[t][0] <= v <= lim[t][1]
    m = re.fullmatch(r"Vec<(.+)>", t)
    return bool(m) and isinstance(v, list) and all(fits(x, m.group(1)) for x in v)


def mutations(v, t: str) -> list:
    """Plausible wrong answers, used to check the spec rejects them."""
    out = []
    if t == "bool":
        out = [not v]
    elif t in SCALARS:
        out = [v + 1, v - 1]
    elif t.startswith("Vec<Vec<"):
        out = [v[:-1], v + [v[-1]]] if v else [[[0]]]
    elif t.startswith("Vec<"):
        inner = t[4:-1]
        if not v:
            out = [[False] if inner == "bool" else [0]]
        else:
            first = (not v[0]) if inner == "bool" else v[0] + 1
            out = [[first] + v[1:], v[:-1], v + [v[-1]]]
    seen, res = {json.dumps(v)}, []
    for m in out:
        k = json.dumps(m)
        if k not in seen and fits(m, t):
            seen.add(k)
            res.append(m)
    return res
