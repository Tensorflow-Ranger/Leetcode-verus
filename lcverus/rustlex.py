"""A small Rust/Verus lexer plus the ghost-code eraser.

The eraser is the core of the "strict fidelity" guarantee: it removes every
Verus-only construct the prover may add (loop specs, proof blocks, asserts,
ghost lets) and the remaining tokens must equal the original rustgym body.
It is deliberately conservative: anything it does not recognise is left in
place, so an unexpected edit shows up as a token mismatch (fail closed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PUNCT = sorted(
    """<==> ==> <== === !== ..= ... :: -> => == != <= >= && || += -= *= /= %= ^= &= |= <<= >>= << >> ..
    + - * / % ^ ! & | = < > @ . , ; : # $ ? ~ ( ) [ ] { }""".split(),
    key=len,
    reverse=True,
)

_ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_number = re.compile(r"(0x[0-9a-fA-F_]+|0o[0-7_]+|0b[01_]+|[0-9][0-9_]*(\.[0-9][0-9_]*)?([eE][+-]?[0-9_]+)?)([a-z][a-z0-9]*)?")


class LexError(ValueError):
    pass


@dataclass(frozen=True)
class Tok:
    text: str
    line: int
    pos: int = 0  # character offset in the source

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.text!r}@{self.line}"


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            if depth:
                raise LexError(f"unterminated block comment at line {line}")
            line += src.count("\n", i, j)
            i = j
        elif c == '"' or (c in "br" and re.match(r'(b?r#*"|b")', src[i:])):
            m = re.match(r'(b?)(r)(#*)"', src[i:])
            if m:  # raw string
                end = '"' + m.group(3)
                j = src.find(end, i + m.end())
                if j < 0:
                    raise LexError(f"unterminated raw string at line {line}")
                j += len(end)
            else:
                j = i + (2 if c == "b" else 1)
                while j < n and src[j] != '"':
                    j += 2 if src[j] == "\\" else 1
                if j >= n:
                    raise LexError(f"unterminated string at line {line}")
                j += 1
            toks.append(Tok(src[i:j], line, i))
            line += src.count("\n", i, j)
            i = j
        elif c == "'":
            m = re.match(r"'(\\(x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]+\}|.)|[^\\'])'", src[i:])
            if m:  # char literal
                toks.append(Tok(m.group(0), line, i))
                i += m.end()
            else:  # lifetime / loop label
                m = _ident.match(src, i + 1)
                if not m:
                    raise LexError(f"bad quote at line {line}")
                toks.append(Tok(src[i : m.end()], line, i))
                i = m.end()
        elif c.isdigit():
            m = _number.match(src, i)
            # don't swallow `..` in ranges like 0..n
            text = m.group(0)
            if "." in text and src.startswith("..", i + text.index(".")):
                text = text[: text.index(".")]
            toks.append(Tok(text, line, i))
            i += len(text)
        elif c.isalpha() or c == "_":
            m = _ident.match(src, i)
            toks.append(Tok(m.group(0), line, i))
            i = m.end()
        else:
            for p in PUNCT:
                if src.startswith(p, i):
                    toks.append(Tok(p, line, i))
                    i += len(p)
                    break
            else:
                raise LexError(f"unexpected character {c!r} at line {line}")
    return toks


OPEN = {"(": ")", "[": "]", "{": "}"}
CLOSE = {")", "]", "}"}


def skip_group(toks: list[Tok], i: int) -> int:
    """toks[i] is an opening bracket; return the index just past its match."""
    stack = []
    for j in range(i, len(toks)):
        t = toks[j].text
        if t in OPEN:
            stack.append(OPEN[t])
        elif t in CLOSE:
            if not stack or stack.pop() != t:
                raise LexError(f"unbalanced {t!r} at line {toks[j].line}")
            if not stack:
                return j + 1
    raise LexError(f"unclosed {toks[i].text!r} at line {toks[i].line}")


def skip_until(toks: list[Tok], i: int, stops: set[str]) -> int:
    """Advance from i to the first token in `stops` at bracket depth 0."""
    while i < len(toks):
        t = toks[i].text
        if t in stops:
            return i
        if t in OPEN:
            i = skip_group(toks, i)
        elif t in CLOSE:
            raise LexError(f"unexpected {t!r} at line {toks[i].line}")
        else:
            i += 1
    raise LexError(f"expected one of {sorted(stops)}")


LOOP_SPEC_KW = {"invariant", "invariant_except_break", "ensures", "decreases"}
GHOST_STMT_KW = {"reveal", "reveal_with_fuel"}


def erase(toks: list[Tok]) -> list[Tok]:
    """Strip Verus ghost/proof constructs from an exec function body."""
    out: list[Tok] = []
    i = 0
    while i < len(toks):
        t = toks[i].text
        nxt = toks[i + 1].text if i + 1 < len(toks) else ""
        if t == "proof" and nxt == "{":
            i = skip_group(toks, i + 1)
        elif t == "assert" and nxt in ("(", "forall"):
            i = _skip_assert(toks, i)
        elif t == "let" and nxt in ("ghost", "tracked"):
            i = skip_until(toks, i, {";"}) + 1
        elif t in GHOST_STMT_KW and nxt == "(":
            i = skip_until(toks, i, {";"}) + 1
        elif t == "broadcast" and nxt == "use":
            i = skip_until(toks, i, {";"}) + 1
        elif t == "in" and i + 2 < len(toks) and _ident.fullmatch(nxt) and toks[i + 2].text == ":":
            out.append(toks[i])  # `for x in it: v` names the ghost iterator `it`; drop `it:`
            i += 3
        elif t in LOOP_SPEC_KW and _in_loop_header(out):
            i = skip_until(toks, i, {"{"})
        elif t == "#" and nxt == "[" and i + 2 < len(toks) and toks[i + 2].text == "verifier":
            i = skip_group(toks, i + 1)
        else:
            out.append(toks[i])
            i += 1
    return out


def _skip_assert(toks: list[Tok], i: int) -> int:
    i += 1
    if toks[i].text == "(":
        i = skip_group(toks, i)
    else:  # assert forall|..| P implies Q by { .. }
        i = skip_until(toks, i, {"by", ";"})
    if i < len(toks) and toks[i].text == "by":
        i += 1
        if toks[i].text == "(":  # by (nonlinear_arith) / by (bit_vector) / by (compute)
            i = skip_group(toks, i)
        if toks[i].text == "requires":
            i = skip_until(toks, i, {"{"})
        if i < len(toks) and toks[i].text == "{":
            i = skip_group(toks, i)
    if i < len(toks) and toks[i].text == ";":
        i += 1
    return i


def _in_loop_header(out: list[Tok]) -> bool:
    """True if we're between `while`/`for`/`loop` and the loop body's `{`."""
    depth = 0
    for tok in reversed(out):
        t = tok.text
        if t in CLOSE:
            depth += 1
        elif t in OPEN:
            if depth == 0:
                return False
            depth -= 1
        elif depth == 0 and t in (";", "}"):
            return False
        elif depth == 0 and t in ("while", "for", "loop"):
            return True
    return False


def texts(toks: list[Tok]) -> list[str]:
    return [t.text for t in toks]


@dataclass
class FnInfo:
    name: str
    sig: str  # `fn name(params) -> Ret` (no body)
    params: list[tuple[str, str, bool]]  # (name, type, is_mut)
    ret: str | None
    body: str  # including the outer braces


def find_fns(src: str) -> list[FnInfo]:
    """Find `fn` items (with bodies) in Rust source; params are parsed shallowly."""
    toks = tokenize(src)
    res = []
    for k, t in enumerate(toks):
        if t.text != "fn" or k + 2 >= len(toks) or toks[k + 2].text not in ("(", "<"):
            continue
        name = toks[k + 1].text
        j = k + 2
        if toks[j].text == "<":
            continue  # generics: out of scope for the pilot
        pend = skip_group(toks, j)
        params = _parse_params(toks[j + 1 : pend - 1])
        ret = None
        b = pend
        if toks[b].text == "->":
            b = skip_until(toks, b, {"{", ";"})
            ret = " ".join(texts(toks[pend + 1 : b]))
        if toks[b].text != "{":
            continue
        e = skip_group(toks, b)
        body = _slice_src(src, toks, b, e)
        sig = _slice_src(src, toks, k, b).strip()
        res.append(FnInfo(name, sig, params, _norm_type(ret) if ret else None, body))
    return res


def _slice_src(src: str, toks: list[Tok], a: int, b: int) -> str:
    """Source text spanning tokens [a, b)."""
    last = toks[b - 1]
    return src[toks[a].pos : last.pos + len(last.text)]


def _parse_params(ptoks: list[Tok]) -> list[tuple[str, str, bool]]:
    params, cur, depth = [], [], 0
    for t in ptoks + [Tok(",", 0)]:
        if t.text in ("<", "(", "["):
            depth += 1
        elif t.text in (">", ")", "]"):
            depth -= 1
        elif t.text == ">>":
            depth -= 2
        if t.text == "," and depth == 0:
            if cur:
                ws = texts(cur)
                mut = ws[0] == "mut"
                if mut:
                    ws = ws[1:]
                if ":" in ws:
                    c = ws.index(":")
                    params.append((" ".join(ws[:c]), _norm_type(" ".join(ws[c + 1 :])), mut))
            cur = []
        else:
            cur.append(t)
    return params


def _norm_type(t: str) -> str:
    return re.sub(r"\s+", "", t)
