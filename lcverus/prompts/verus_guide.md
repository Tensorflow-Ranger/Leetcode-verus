## Verus quick reference (this Verus version; follow it exactly)

Spec language
- Mathematical types: `int`, `nat`, `Seq<T>`. Spec arithmetic on `int` never overflows; cast with `x as int`.
- `v@` is the `Seq` view of a `Vec`; `grid.deep_view()` is the `Seq<Seq<i32>>` view of a `Vec<Vec<i32>>`.
- In spec code index a `Seq` with an `int`: `s[i]`, length `s.len()` (a `nat`).
- Quantifiers: `forall|i: int| 0 <= i < s.len() ==> P(s[i])`, `exists|i: int, j: int| 0 <= i < j < s.len() && Q(i, j)`.
  Put `#[trigger]` on a sub-term that mentions every bound variable when Verus complains about triggers.
- Useful `Seq` ops: `s.subrange(lo, hi)`, `s.take(n)`, `s.skip(n)`, `s.drop_last()`, `s.last()`, `s.push(x)`,
  `s.map_values(|x: i32| x as int)`, `s.filter(|x: i32| x > 0)`, `s.to_multiset()`, `s.contains(x)`;
  extensional equality `s1 =~= s2`.
- Recursive spec fns need `decreases`, e.g.
  `spec fn sum(s: Seq<i32>) -> int decreases s.len() { if s.len() == 0 { 0 } else { sum(s.drop_last()) + s.last() as int } }`
- `if c { a } else { b }` and `let x = ..;` work inside spec fns. `==>`, `<==>`, `&&`, `||`, `!`.

Spec-syntax pitfalls (each one has made Verus reject a spec)
- A conjunction list is written `&&& a &&& b` (each on its own line) or `a && b`; an expression may not start with `&&`.
- Integer literals whose type Verus cannot infer need a suffix: `1int`, `0nat` (or compare against a typed value).
- Every quantifier needs a trigger: put `#[trigger]` on a term mentioning all bound variables (`#[trigger] s[i]`).
- A `spec fn` precondition is `recommends`, not `requires`.

Exec (executable) code — what Verus proves automatically
- Every `v[i]` must be in bounds, every `+ - * /` and `as` cast must not overflow, `usize` subtraction must not
  underflow, division by zero is impossible. These are proof obligations: the precondition `pre(..)` gives the
  bounds from the LeetCode constraints, and loop invariants must carry them.
- `while` loops need `decreases <expr>` (termination) and usually `invariant` clauses:
  ```
  while i < n
      invariant
          0 <= i <= n,
          acc as int == f(v@.subrange(0, i as int)),
      decreases n - i,
  { .. }
  ```
  `for i in 0..n` loops need `invariant` (bounds on `i` are implicit) but no `decreases`.
  `for x in v` (iterating a Vec by value) — name the ghost iterator with `it:` to talk about progress:
  ```
  for x in it: nums
      invariant
          it.seq() == nums@,                       // the sequence being iterated
          c == cnt(nums@.take(it.index())),        // it.index() = number of items consumed so far
  { .. }
  ```
  `loop { .. }` needs `decreases` too. Loops here run with `loop_isolation(false)`, so facts established before
  the loop are visible inside it, but anything the loop *modifies* must be described by invariants.
- `invariant` must hold on entry and be re-established at the end of every iteration; `break`/`return` inside
  a loop must leave enough facts to prove the postcondition.
- Ghost/proof code you may add inside the body:
  `assert(P);`, `assert(P) by { lemma_x(a); }`, `assert(x * y <= 100 * 100) by (nonlinear_arith) requires x <= 100, y <= 100;`,
  `assert(a & b == b & a) by (bit_vector);`, `proof { lemma_x(..); assert(..); }`, `let ghost old_v = v@;`
- Multiplication facts usually need `by (nonlinear_arith)`; extensional Seq facts need `=~=`.
- Lemmas are `proof fn` with `requires`/`ensures`; recursive lemmas need `decreases`. Call them from `proof { }`.
- `i32::MAX`, `i32::MIN`, `a.max(b)`, `i32::min(a, b)`, `v.len()`, `v.push(x)`, `vec![..]` all have specs.

Common mistakes (each one has cost earlier attempts a round)
- `s.len()` is a `nat`; `take`, `skip`, `subrange` and `Seq` indices want an `int`: write `s.take(s.len() as int)`,
  `s.subrange(0, i as int)`, `v@[i as int]`.
- The ghost iterator `it` of `for x in it: v` exists only inside that loop (its invariants and body). After the loop,
  use only facts the invariants carried out (e.g. state them in terms of `v@` and ordinary variables).
- Keep proofs small. One or two focused lemmas with clear `requires`/`ensures` beat many large ones; first make
  the loop invariant strong enough, then add lemmas only for the facts Verus reports it cannot prove.
- Facts about `s.skip(1)[i]`, `s.drop_last()[i]`, `s.take(n)[i]` usually need the index relationship asserted
  explicitly (`assert(s.skip(1)[i] == s[i + 1]);`) and extensional equalities need `=~=`.
