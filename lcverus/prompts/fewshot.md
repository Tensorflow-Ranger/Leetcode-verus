## Worked example A (verified with this Verus version)

Problem: return the smallest index `i` with `a[i] == i`, or `-1`. Constraints: `1 <= a.length < 10^4`, `-10^9 <= a[i] <= 10^9`.

Original rustgym code:
```rust
fn fixed_point(a: Vec<i32>) -> i32 {
    for i in 0..a.len() {
        if i as i32 == a[i] {
            return i as i32;
        }
    }
    -1
}
```

Spec:
```rust
spec fn pre(a: Seq<i32>) -> bool {
    1 <= a.len() < 10000 && forall|i: int| 0 <= i < a.len() ==> -1000000000 <= #[trigger] a[i] <= 1000000000
}
spec fn post(a: Seq<i32>, result: i32) -> bool {
    if exists|i: int| 0 <= i < a.len() && a[i] == i {
        0 <= result < a.len() && a[result as int] == result && forall|j: int| 0 <= j < result ==> a[j] != j
    } else {
        result == -1
    }
}
```

Annotated body (erases back to the original exactly):
```rust
{
    for i in 0..a.len()
        invariant
            forall|j: int| 0 <= j < i ==> a@[j] != j,
    {
        if i as i32 == a[i] {
            return i as i32;
        }
    }
    -1
}
```

## Worked example B (verified with this Verus version)

Problem: return the sum of the array. Constraints: `1 <= a.length <= 1000`, `-1000 <= a[i] <= 1000`.

Original rustgym code:
```rust
fn total(a: Vec<i32>) -> i32 {
    let mut s = 0;
    let mut i = 0;
    while i < a.len() {
        s += a[i];
        i += 1;
    }
    s
}
```

Spec:
```rust
spec fn sum(s: Seq<i32>) -> int
    decreases s.len(),
{
    if s.len() == 0 { 0 } else { sum(s.drop_last()) + s.last() as int }
}
spec fn pre(a: Seq<i32>) -> bool {
    1 <= a.len() <= 1000 && forall|i: int| 0 <= i < a.len() ==> -1000 <= #[trigger] a[i] <= 1000
}
spec fn post(a: Seq<i32>, result: i32) -> bool {
    result as int == sum(a)
}
```

Lemmas:
```rust
proof fn lemma_sum_bounds(s: Seq<i32>)
    requires forall|i: int| 0 <= i < s.len() ==> -1000 <= #[trigger] s[i] <= 1000,
    ensures -1000 * s.len() <= sum(s) <= 1000 * s.len(),
    decreases s.len(),
{
    if s.len() > 0 {
        lemma_sum_bounds(s.drop_last());
    }
}
```

Annotated body (the `s += a[i]` overflow check is discharged by the bounds lemma):
```rust
{
    let mut s = 0;
    let mut i = 0;
    while i < a.len()
        invariant
            0 <= i <= a.len(),
            s as int == sum(a@.subrange(0, i as int)),
        decreases a.len() - i,
    {
        proof {
            assert(a@.subrange(0, i as int + 1).drop_last() =~= a@.subrange(0, i as int));
            lemma_sum_bounds(a@.subrange(0, i as int + 1));
        }
        s += a[i];
        i += 1;
    }
    assert(a@.subrange(0, a.len() as int) =~= a@);
    s
}
```
