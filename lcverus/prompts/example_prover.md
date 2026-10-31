You help Verus/Z3 prove a concrete fact about a specification applied to a LeetCode example. The proof fn
below failed (Z3 could not find the proof by itself). Provide proof hints that make it verify. Typical hints:
- for `exists` goals, assert the witness instance, e.g. `assert(area(h, 1, 8) == 49);`
- for `forall` goals over small concrete ranges, use `assert forall|i: int| 0 <= i < 5 implies P(i) by { ... }`
  and inside, case-split: `assert(i == 0 || i == 1 || i == 2 || i == 3 || i == 4);`
- unfold recursive spec fns step by step with intermediate asserts, or `reveal_with_fuel(f, 10);`
- name the literal first: `let s = seq![...];` then `assert(s[3] == 7);` etc.
You may NOT use `assume`, `admit`, or any attribute. If the fact is actually FALSE (the spec disagrees with
the example), say so instead of giving hints.

{{VERUS_GUIDE}}

Answer format (nothing else is parsed). Either
<hints>
```rust
// statements placed inside the proof fn, before its final assert
```
</hints>
or
<false>explanation of why the spec and the example disagree</false>
