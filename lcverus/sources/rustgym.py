"""Scan rustgym leetcode solutions: `leetcode/src/d*/_<id>_<slug>.rs`."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from ..rustlex import LexError, find_fns

FNAME = re.compile(r"_(\d+)_(\w+)\.rs$")


@dataclass
class Source:
    pid: int
    name_slug: str  # from the file name, e.g. container_with_most_water
    path: str
    solution: str  # code before the first #[test]
    tests: str  # the #[test] section
    uses: list[str]
    fns: list[dict]  # FnInfo dicts for every fn in the solution

    def to_dict(self) -> dict:
        return asdict(self)


def parse_file(path: Path) -> Source | None:
    m = FNAME.search(path.name)
    if not m:
        return None
    text = path.read_text()
    cut = text.find("#[test]")
    solution, tests = (text, "") if cut < 0 else (text[:cut], text[cut:])
    uses = [ln.strip() for ln in solution.splitlines() if ln.strip().startswith("use ")]
    try:
        fns = [f.__dict__ for f in find_fns(solution)]
    except LexError:
        fns = []
    return Source(int(m.group(1)), m.group(2), str(path), solution, tests, uses, fns)


def scan(root: Path) -> dict[int, Source]:
    out = {}
    for p in sorted(root.glob("d*/_*.rs")):
        s = parse_file(p)
        if s and s.pid not in out:
            out[s.pid] = s
    return out


def shape_issue(src: Source, allowed_types: set[str]) -> str | None:
    """Why this solution is outside the pilot's shape, or None if it fits."""
    if "impl Solution" not in src.solution:
        return "shape:not_impl_solution"
    if len(src.fns) != 1:
        return "shape:helper_fns" if src.fns else "shape:no_fn"
    f = src.fns[0]
    for _, t, _ in f["params"]:
        if t not in allowed_types:
            return f"shape:param_type:{t}"
    if f["ret"] and f["ret"] not in allowed_types:
        return f"shape:return_type:{f['ret']}"
    if not f["ret"]:
        return "shape:no_return"
    return None
