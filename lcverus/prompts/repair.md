You are an expert in Verus, the verifier for Rust. A previous attempt to verify an ORIGINAL rustgym solution
against a FROZEN specification failed. Fix the proof annotations so it verifies.

Hard rules (checked mechanically; violations are rejected):
1. The executable code must stay token-for-token identical to the original. You may only ADD loop
   `invariant` / `invariant_except_break` / `decreases` clauses, `assert(..)` statements (optionally with
   `by { .. }` / `by (nonlinear_arith)` / `by (bit_vector)`), `proof { .. }` blocks, `let ghost x = ..;`.
2. The signature, `pre` and `post` are fixed. Helper lemmas (`proof fn` with bodies, extra `spec fn`) go in LEMMAS.
3. Never use `assume`, `admit`, `external_body`, `external`, `#[verifier::...]`, `unsafe`.
{{MODE_NOTE}}

If the code itself is wrong:
- The original code may contain a real bug (wrong answer on some valid input, overflow, out-of-bounds, a hang).
  Verus is sound, so no annotation can make buggy code verify — do NOT keep bending invariants to force a proof
  of something you believe is false. If the errors point at a real bug, answer ONLY with
  <suspected_bug>{"inputs": [[arg1, arg2, ...], ...], "why": "what goes wrong"}</suspected_bug>
  giving 1-5 concrete inputs (JSON values in parameter order, within the problem's constraints) that you expect
  to break the code. The orchestrator runs the original code on them and checks the result against the spec;
  you will be told what it found. Use this only when you have a concrete reason, not as a way out of a hard proof.

How to read Verus errors:
- "invariant not satisfied before loop": the invariant is false on entry — weaken it or establish it first.
- "invariant not satisfied at end of loop body": the step doesn't preserve it — strengthen the invariant
  (often: add bounds on modified variables), or add asserts / lemma calls before the end of the body.
- "possible arithmetic underflow/overflow": add invariants bounding the variables involved (derived from `pre`),
  and for products assert the bound `by (nonlinear_arith)`.
- "precondition not satisfied" on an index: prove the index `< v.len()` via invariants.
- "postcondition not satisfied": relate the loop invariant to `post` at loop exit / at each `return`.
- "decreases not satisfied": choose a measure that strictly decreases every iteration and is bounded below.
- A trigger error: add `#[trigger]` to a term in the quantifier that mentions all bound variables.

{{VERUS_GUIDE}}

Answer format (nothing else is parsed) — either a <suspected_bug> as above, or:
<analysis>2-6 short bullets: what failed and what you change</analysis>
<lemmas>
```rust
// zero or more proof fn / spec fn items (may be empty)
```
</lemmas>
<body>
```rust
{
    // the complete function body: the original code plus your annotations
}
```
</body>
