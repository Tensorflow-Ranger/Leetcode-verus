You fix Verus compile errors in a specification WITHOUT changing what it means. The spec below was written for a
LeetCode problem; Verus rejected it for syntax/typing/trigger reasons only. Return the same spec with the
smallest edits that make it compile: same functions, same names and signatures, same logical content.

Typical fixes:
- integer literals in spec code need a type when Verus cannot infer one: `1int`, `0nat`, or cast the other side;
- a quantifier without a usable trigger: add `#[trigger]` to a sub-term that mentions every bound variable,
  e.g. `forall|i: int| 0 <= i < s.len() ==> -1000 <= #[trigger] s[i] <= 1000`;
- `spec fn` preconditions are written `recommends`, never `requires`;
- a leading `&&` at the start of an expression is not allowed: use `&&& a &&& b` (one per line) or `a && b`;
- recursive spec fns need `decreases`.

{{VERUS_GUIDE}}

Answer format (nothing else is parsed):
<spec_fns>
```rust
// the fixed spec
```
</spec_fns>
