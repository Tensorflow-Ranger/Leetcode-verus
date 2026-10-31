"""Run Verus and parse its diagnostics into structured errors."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import load

_sem: threading.BoundedSemaphore | None = None
_sem_lock = threading.Lock()


def _semaphore() -> threading.BoundedSemaphore:
    global _sem
    with _sem_lock:
        if _sem is None:
            _sem = threading.BoundedSemaphore(load()["verus"]["max_parallel"])
    return _sem


KINDS = [
    ("precondition", r"precondition not satisfied"),
    ("postcondition", r"postcondition not satisfied"),
    ("invariant_entry", r"invariant not satisfied before loop"),
    ("invariant_end", r"invariant not satisfied at end of loop body"),
    ("invariant", r"invariant not satisfied"),
    ("overflow", r"possible arithmetic underflow/overflow"),
    ("decreases", r"decreases|termination"),
    ("assertion", r"assertion failed"),
    ("bounds", r"index out of bounds|requires.*len"),
    ("timeout", r"Resource limit|rlimit|timed out"),
    ("type", r"^error\[E\d+\]|mismatched types|cannot find|expected"),
    ("unsupported", r"is not supported"),
]


@dataclass
class VerusError:
    kind: str
    message: str
    line: int | None
    block: str  # full diagnostic text as printed by Verus


@dataclass
class VerusResult:
    ok: bool
    verified: int = 0
    errors_count: int = 0
    errors: list[VerusError] = field(default_factory=list)
    timed_out: bool = False
    crashed: bool = False
    seconds: float = 0.0
    raw: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["raw"] = self.raw[-20000:]
        return d

    def feedback(self, limit: int = 12000) -> str:
        if self.timed_out:
            return "Verus timed out (the proof is too expensive; simplify invariants / add helper lemmas)."
        if self.crashed:
            return "Verus crashed internally:\n" + self.raw[-3000:]
        text = "\n\n".join(e.block for e in self.errors) or self.raw
        return text[:limit]


def _env() -> dict:
    cfg = load()
    env = dict(os.environ)
    env["PATH"] = f"{Path.home() / '.cargo' / 'bin'}:{env.get('PATH', '')}"
    env["VERUS_Z3_PATH"] = str(cfg.z3_bin)
    env.pop("RUSTUP_TOOLCHAIN", None)
    return env


def run(path: Path, *, no_verify: bool = False, compile_to: Path | None = None, timeout: int | None = None) -> VerusResult:
    cfg = load()
    path = path.resolve()
    args = [str(cfg.verus_bin), str(path), "--expand-errors", "--multiple-errors", "8", "--rlimit", str(cfg["verus"]["rlimit"])]
    if no_verify:
        args.append("--no-verify")
    if compile_to is not None:
        args += ["--compile", "-o", str(compile_to)]
    else:
        args += ["--crate-type=lib"]
    timeout = timeout or cfg["verus"]["timeout_s"]
    t0 = time.time()
    with _semaphore():
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=_env(), cwd=path.parent)
        except subprocess.TimeoutExpired as e:
            raw = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            return VerusResult(ok=False, timed_out=True, seconds=time.time() - t0, raw=raw)
    raw = "\n".join(ln for ln in (p.stdout + p.stderr).splitlines() if "weak version `GLIBC" not in ln)
    return parse(raw, p.returncode, time.time() - t0)


def parse(raw: str, returncode: int, seconds: float = 0.0) -> VerusResult:
    res = VerusResult(ok=False, seconds=seconds, raw=raw)
    m = re.search(r"verification results::\s*(\d+) verified,\s*(\d+) errors", raw)
    if m:
        res.verified, res.errors_count = int(m.group(1)), int(m.group(2))
    res.crashed = "panicked at" in raw and not m
    res.errors = _split_errors(raw)
    res.ok = returncode == 0 and not res.errors and not res.crashed
    return res


def _split_errors(raw: str) -> list[VerusError]:
    blocks, cur = [], None
    for ln in raw.splitlines():
        if re.match(r"^error(\[E\d+\])?:", ln):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif re.match(r"^(warning|note: )", ln) or ln.startswith("verification results::"):
            if cur:
                blocks.append(cur)
            cur = None
        elif cur is not None:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        head = b[0]
        if re.match(r"^error: aborting due to", head) or "could not compile" in head:
            continue
        text = "\n".join(b).rstrip()
        lm = re.search(r"-->\s*\S+?:(\d+):\d+", text)
        kind = "other"
        for k, pat in KINDS:
            if re.search(pat, head):
                kind = k
                break
        out.append(VerusError(kind, head.removeprefix("error: "), int(lm.group(1)) if lm else None, text))
    return out


def errors_by_fn(res: VerusResult, ranges: dict[str, tuple[int, int]]) -> dict[str, list[VerusError]]:
    """Attribute errors to functions by line range (used for per-example checks)."""
    out: dict[str, list[VerusError]] = {}
    for e in res.errors:
        for name, (a, b) in ranges.items():
            if e.line is not None and a <= e.line <= b:
                out.setdefault(name, []).append(e)
    return out
