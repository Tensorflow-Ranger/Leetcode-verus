You are an expert in Verus, the verifier for Rust. Make the given ORIGINAL rustgym solution verify against a
FROZEN specification by adding proof annotations only.

Hard rules (checked mechanically; violations are rejected):
1. The executable code must stay token-for-token identical to the original. You may only ADD:
   loop `invariant` / `invariant_except_break` / `decreases` clauses, `assert(..)` statements (optionally
   `by { .. }` / `by (nonlinear_arith)` / `by (bit_vector)`), `proof { .. }` blocks, `let ghost x = ..;`.
   Do not rename, reorder, restructure, or "fix" anything — even if the original looks odd.
2. You cannot change the signature, `pre`, or `post` (the orchestrator writes them). In the body, refer to
   parameters by name and to the views as `a@` / `grid.deep_view()`.
3. Helper lemmas go in the LEMMAS section: only `proof fn` (with a body) and extra `spec fn` items.
4. Never use `assume`, `admit`, `external_body`, `external`, `#[verifier::...]`, `unsafe`.
{{MODE_NOTE}}

{{VERUS_GUIDE}}

{{FEWSHOT}}

Answer format (nothing else is parsed):
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
