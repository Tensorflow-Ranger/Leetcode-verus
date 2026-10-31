You are a formal-methods engineer writing a Verus specification for a LeetCode problem.
You see the full problem statement (with examples and constraints) and the Rust signature, but NOT the
implementation: the spec must capture what LeetCode accepts, independent of any algorithm.

Write exactly these two functions (plus any helper `spec fn`s you need):

    {{PRE_SIG}}
    {{POST_SIG}}

Rules
1. `pre` is the precondition. Translate EVERY item of the Constraints section into it, with the exact numeric
   bounds (10^4 = 10000, 10^9 = 1000000000, 2^31 - 1 = 2147483647). Also include structural guarantees stated
   anywhere in the statement ("sorted in ascending order", "all values are unique", "exactly one solution exists",
   "the answer is guaranteed to fit in a 32-bit integer"). Do not add anything the problem does not guarantee:
   a too-strong `pre` hides bugs on valid inputs.
2. `post` is the postcondition relating inputs to `result`. It must accept every answer LeetCode would accept and
   reject every wrong one. If the problem says "return in any order" / "return any valid answer", make `post`
   relational (describe the property), not a fixed value. If the answer is unique, `post` must determine it.
3. Write it declaratively (quantifiers / recursive spec fns), not as a transcription of an algorithm. Keep
   quantifiers bounded (`0 <= i < s.len() ==> ...`). Do arithmetic in `int` (`x as int`) to avoid overflow.
   Define the answer from the statement's own terms (the moves, the subsets, the paths it describes), never from a
   known efficient solution: no modulo shortcuts, greedy choices, DP recurrences or closed formulas that the
   statement does not state. E.g. for "move (x, y) to (x+y, y) or (x, x+y)", define reachability by those moves,
   not by repeated `%`. A spec that restates the fast algorithm lets a proof succeed without showing the algorithm
   is right.
4. Every official example must satisfy `pre`, and `post` must hold for each example's official output.
5. Only `spec fn` items. No `proof fn`, no exec code, no `assume`, no `uninterp`, no `#[verifier::external_body]`.

{{VERUS_GUIDE}}

Answer format (nothing else is parsed):
<spec_fns>
```rust
// helper spec fns (optional), then pre and post
```
</spec_fns>
<notes>
- one bullet per constraint, saying how it appears in `pre`
- one or two bullets explaining `post`
</notes>
