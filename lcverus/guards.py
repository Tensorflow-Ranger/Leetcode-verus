"""Deterministic integrity checks: the part of the pipeline that is trusted.

A Verus "verified" verdict only means something if
  1. the executable code is exactly the rustgym code (strict fidelity),
  2. the spec (pre/post) is the frozen one,
  3. nothing was assumed rather than proved.
(2) holds by construction — the orchestrator writes the signature and the
requires/ensures itself and only splices in the LLM's lemmas and body — and
`spec_hash` double-checks it. (1) and (3) are checked here.
"""

from __future__ import annotations

import difflib
import hashlib

from .rustlex import LexError, Tok, erase, skip_group, skip_until, texts, tokenize

# Identifiers that would let a proof succeed without proving anything.
BANNED = {
    "assume",
    "admit",
    "external_body",
    "external",
    "external_fn_specification",
    "assume_specification",
    "exec_allows_no_decreases_clause",
    "assume_termination",
    "unsafe",
    "truncate",
    "uninterp",
    "transmute",
    "inline_air_stmt",
    "allow_in_spec",
}
VERIFIER_ATTR_OK = {"spinoff_prover", "rlimit", "nonlinear", "opaque"}
SPEC_FN_ALLOWED_PREFIX = {"spec", "proof", "open", "closed", "pub", "broadcast"}


def spec_hash(spec_fns: str) -> str:
    return hashlib.sha256(" ".join(texts(tokenize(spec_fns))).encode()).hexdigest()[:16]


def _banned(toks: list[Tok], where: str) -> list[str]:
    out = []
    for k, t in enumerate(toks):
        if t.text in BANNED:
            out.append(f"{where}: banned construct `{t.text}` (line {t.line})")
        if t.text == "#" and k + 2 < len(toks) and toks[k + 1].text == "[" and toks[k + 2].text == "verifier":
            attr = toks[k + 4].text if k + 4 < len(toks) else ""
            if attr not in VERIFIER_ATTR_OK:
                out.append(f"{where}: attribute `#[verifier::{attr}]` not allowed (line {t.line})")
    return out


def check_items(src: str, where: str, allow_proof: bool) -> list[str]:
    """Lemma/spec sections may only contain spec fns (and proof fns, with bodies)."""
    try:
        toks = tokenize(src)
    except LexError as e:
        return [f"{where}: cannot lex: {e}"]
    errs = _banned(toks, where)
    i = 0
    while i < len(toks):
        t = toks[i].text
        if t == "#":  # attribute
            try:
                i = skip_group(toks, i + 1)
            except LexError as e:
                return errs + [f"{where}: {e}"]
            continue
        if t == "broadcast" and i + 1 < len(toks) and toks[i + 1].text in ("use", "group"):
            try:
                j = skip_until(toks, i, {";", "{"})
                i = skip_group(toks, j) if toks[j].text == "{" else j + 1
            except LexError as e:
                return errs + [f"{where}: {e}"]
            continue
        # item header: modifiers then `fn`
        j = i
        mods = []
        while j < len(toks) and toks[j].text in SPEC_FN_ALLOWED_PREFIX | {"(", ")", "crate"}:
            mods.append(toks[j].text)
            j += 1
        if j >= len(toks) or toks[j].text != "fn":
            return errs + [f"{where}: only spec/proof fns are allowed here, found `{t}` (line {toks[i].line})"]
        kind = "proof" if "proof" in mods else "spec" if "spec" in mods else "exec"
        if kind == "exec":
            return errs + [f"{where}: exec fn `{toks[j + 1].text}` not allowed (line {toks[j].line})"]
        if kind == "proof" and not allow_proof:
            return errs + [f"{where}: proof fns not allowed in the spec section (line {toks[j].line})"]
        try:
            k = _fn_body(toks, j + 2)
        except LexError as e:
            return errs + [f"{where}: {e}"]
        if toks[k].text == ";":
            errs.append(f"{where}: bodiless fn `{toks[j + 1].text}` is an axiom (line {toks[j].line})")
            i = k + 1
        else:
            i = skip_group(toks, k)
    return errs


ITEM_START = SPEC_FN_ALLOWED_PREFIX | {"fn", "#", "impl", "struct", "enum", "trait", "mod", "use", "const", "static", "type"}


def _fn_body(toks: list[Tok], i: int) -> int:
    """Index of the fn body's `{` (or of a terminating `;`), scanning from the params.

    Spec clauses may contain brace groups themselves (`ensures if c { a } else { b }`), so the
    body is the depth-0 brace group that is followed by the next item or by the end of input.
    """
    while i < len(toks):
        t = toks[i].text
        if t == ";":
            return i
        if t == "{":
            end = skip_group(toks, i)
            if end >= len(toks) or toks[end].text in ITEM_START:
                return i
            i = end
        elif t in ("(", "["):
            i = skip_group(toks, i)
        elif t in (")", "]", "}"):
            raise LexError(f"unexpected {t!r} at line {toks[i].line}")
        else:
            i += 1
    raise LexError("fn without body")


def check_body(body: str, original_body: str) -> list[str]:
    """The LLM's annotated body must erase to the original body, token for token."""
    try:
        toks = tokenize(body)
    except LexError as e:
        return [f"body: cannot lex: {e}"]
    errs = _banned(toks, "body")
    try:
        got = texts(erase(toks))
    except LexError as e:
        return errs + [f"body: cannot erase ghost code: {e}"]
    want = texts(tokenize(original_body))
    if got != want:
        errs.append("body: executable code differs from the original rustgym code:\n" + token_diff(want, got))
    return errs


def token_diff(want: list[str], got: list[str], ctx: int = 6) -> str:
    sm = difflib.SequenceMatcher(a=want, b=got, autojunk=False)
    parts = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            continue
        before = " ".join(want[max(0, a1 - ctx) : a1])
        parts.append(
            f"  near `... {before}`: original has `{' '.join(want[a1:a2]) or '∅'}`, yours has `{' '.join(got[b1:b2]) or '∅'}`"
        )
        if len(parts) >= 5:
            break
    return "\n".join(parts)


def check_candidate(lemmas: str, body: str, original_body: str) -> list[str]:
    return check_items(lemmas, "lemmas", allow_proof=True) + check_body(body, original_body)


def check_spec(spec_fns: str) -> list[str]:
    errs = check_items(spec_fns, "spec", allow_proof=False)
    names = set(texts(tokenize(spec_fns))) if not errs else set()
    for required in ("pre", "post"):
        if not errs and required not in names:
            errs.append(f"spec: missing `spec fn {required}`")
    return errs
