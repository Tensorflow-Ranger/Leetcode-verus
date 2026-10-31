# lcverus report

## Outcome

| status | count |
|---|---|
| verified | 13 |
| bug | 1 |
| error | 12 |
| paused | 15 |

- **verified**: functional spec (`post`) + panic-freedom + termination proved for the unmodified rustgym code.
- **panic_free**: functional proof failed, but no out-of-bounds / overflow / div-by-zero / non-termination proved under `pre`.

### Why problems were skipped

| reason | count |
|---|---|
| `error:write_spec` | 12 |

## Problems

| id | title | status | spec rounds | proof rounds | examples pre / post / neg rejected | critic | runtime | LLM tokens (in/out) | wall s |
|---|---|---|---|---|---|---|---|---|---|
| [9](problems/p9.md) | Palindrome Number (Easy) | bug:panic | 2 | 1 functional | 3/3 / 3/3 / 3/3 | accept | – | 12637/78834 | 647 |
| [42](problems/p42.md) | Trapping Rain Water (Hard) | verified | 1 | 3 functional | 2/2 / 2/2 / 4/4 | accept | ex 2/2, tests pass | 37541/191715 | 907 |
| [84](problems/p84.md) | Largest Rectangle in Histogram (Hard) | verified | 2 | 5 functional | 2/2 / 2/2 / 4/4 | accept | ex 2/2, tests pass | 73158/383386 | 2050 |
| [118](problems/p118.md) | Pascal's Triangle (Easy) | paused:verify | 1 | 8 functional + 8 safety | 2/2 / 2/2 / 4/4 | accept | – | 57873/427237 | 2391 |
| [119](problems/p119.md) | Pascal's Triangle II (Easy) | paused:repair | 3 | 2 functional | 3/3 / 2/3 / 8/9 | accept | – | 38925/265015 | 1873 |
| [169](problems/p169.md) | Majority Element (Easy) | verified | 2 | 4 functional | 2/2 / 2/2 / 4/4 | accept | ex 2/2, tests pass | 32486/220898 | 1379 |
| [174](problems/p174.md) | Dungeon Game (Hard) | paused:repair | 2 | 5 functional | 2/2 / 2/2 / 4/4 | accept | – | 62550/308482 | 1664 |
| [190](problems/p190.md) | Reverse Bits (Easy) | paused:repair | 2 | 1 functional | 2/2 / 2/2 / 4/4 | accept | – | 26673/210789 | 1589 |
| [217](problems/p217.md) | Contains Duplicate (Easy) | verified | 2 | 1 functional | 3/3 / 3/3 / 3/3 | accept | ex 3/3, tests pass | 8789/51257 | 384 |
| [219](problems/p219.md) | Contains Duplicate II (Easy) | paused:find_counterexample | 2 | 8 functional | 3/3 / 3/3 / 3/3 | accept | – | 96428/371643 | 2245 |
| [231](problems/p231.md) | Power of Two (Easy) | verified | 2 | 4 functional | 3/3 / 3/3 / 3/3 | accept | ex 3/3, tests pass | 52103/301502 | 2111 |
| [233](problems/p233.md) | Number of Digit One (Hard) | verified | 1 | 7 functional | 2/2 / 2/2 / 4/4 | accept | ex 2/2, tests pass | 83326/396242 | 2202 |
| [263](problems/p263.md) | Ugly Number (Easy) | verified | 3 | 3 functional | 3/3 / 3/3 / 3/3 | accept | ex 3/3, tests pass | 38589/174584 | 1206 |
| [268](problems/p268.md) | Missing Number (Easy) | verified | 1 | 6 functional | 3/3 / 3/3 / 6/6 | accept | ex 3/3, tests pass | 76487/475158 | 2633 |
| [292](problems/p292.md) | Nim Game (Easy) | verified | 1 | 1 functional | 3/3 / 3/3 / 3/3 | accept | ex 3/3, tests pass | 6151/7408 | 73 |
| [326](problems/p326.md) | Power of Three (Easy) | paused:verify | 2 | 56 functional | 3/3 / 3/3 / 3/3 | accept | – | 24733/117968 | 1150 |
| [330](problems/p330.md) | Patching Array (Hard) | paused:check_spec | 1 | – | – / – / – | – | – | 2299/10635 | 50 |
| [342](problems/p342.md) | Power of Four (Easy) | verified | 2 | 2 functional | 3/3 / 3/3 / 3/3 | accept | ex 3/3, tests pass | 26441/106965 | 970 |
| [367](problems/p367.md) | Valid Perfect Square (Easy) | paused:repair | 2 | 1 functional | 2/2 / 2/2 / 2/2 | accept | – | 25572/107437 | 852 |
| [414](problems/p414.md) | Third Maximum Number (Easy) | paused:prove | 1 | – | 3/3 / 3/3 / 6/6 | accept | – | 4002/29973 | 388 |
| [440](problems/p440.md) | K-th Smallest in Lexicographical Order (Hard) | paused:repair | 1 | 4 functional | 2/2 / 2/2 / 4/4 | accept | – | 68509/426755 | 2323 |
| [446](problems/p446.md) | Arithmetic Slices II - Subsequence (Hard) | paused:find_counterexample | 3 | 6 functional | 2/2 / 2/2 / 4/4 | accept | – | 86538/444990 | 2433 |
| [461](problems/p461.md) | Hamming Distance (Easy) | paused:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [463](problems/p463.md) | Island Perimeter (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [476](problems/p476.md) | Number Complement (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [485](problems/p485.md) | Max Consecutive Ones (Easy) | verified | 2 | 8 functional | 2/2 / 2/2 / 4/4 | accept | ex 2/2, tests pass | 88362/326198 | 1948 |
| [495](problems/p495.md) | Teemo Attacking (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [496](problems/p496.md) | Next Greater Element I (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [507](problems/p507.md) | Perfect Number (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [509](problems/p509.md) | Fibonacci Number (Easy) | verified | 1 | 3 functional | 3/3 / 3/3 / 6/6 | accept | ex 3/3, tests pass | 16039/101866 | 571 |
| [566](problems/p566.md) | Reshape the Matrix (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [575](problems/p575.md) | Distribute Candies (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [598](problems/p598.md) | Range Addition II (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [605](problems/p605.md) | Can Place Flowers (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [645](problems/p645.md) | Set Mismatch (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [674](problems/p674.md) | Longest Continuous Increasing Subsequence (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 1 |
| [693](problems/p693.md) | Binary Number with Alternating Bits (Easy) | error:write_spec | 0 | – | – / – / – | – | – | 0/0 | 2 |
| [780](problems/p780.md) | Reaching Points (Hard) | verified | 2 | 6 functional | 3/3 / 3/3 / 3/3 | accept | ex 3/3, tests pass | 70564/429568 | 2277 |
| [801](problems/p801.md) | Minimum Swaps To Make Sequences Increasing (Hard) | paused:check_spec | 1 | – | – / – / – | – | – | 2371/11506 | 52 |
| [829](problems/p829.md) | Consecutive Numbers Sum (Hard) | paused:triage | 0 | – | – / – / – | – | – | 0/0 | 0 |
| [847](problems/p847.md) | Shortest Path Visiting All Nodes (Hard) | paused:triage | 0 | – | – / – / – | – | – | 0/0 | 0 |

## Where the time and tokens go (per LangGraph node)

| node | runs | wall s | LLM calls (cached) | tokens in | tokens out | Verus calls | Verus s |
|---|---|---|---|---|---|---|---|
| fetch | 41 | 0 | 0 (0) | 0 | 0 | 0 | 0 |
| triage | 39 | 51 | 0 (0) | 0 | 0 | 39 | 51 |
| write_spec | 57 | 6435 | 45 (0) | 104822 | 629217 | 0 | 0 |
| check_spec | 43 | 3470 | 99 (0) | 194875 | 556045 | 271 | 657 |
| critic_spec | 24 | 1783 | 24 (0) | 32910 | 175627 | 0 | 0 |
| prove | 23 | 8305 | 22 (1) | 96790 | 1582078 | 0 | 0 |
| verify | 153 | 560 | 0 (0) | 0 | 0 | 76 | 558 |
| repair | 132 | 15703 | 61 (0) | 689258 | 3034679 | 0 | 0 |
| safety_fallback | 1 | 0 | 0 (0) | 0 | 0 | 0 | 0 |
| runtime | 13 | 15 | 0 (0) | 0 | 0 | 13 | 15 |

## Orchestration (LangGraph) at work

- **Checkpoints written**: 659 across 41 threads (one thread per problem; any run can resume from its last node).
- **Resumed runs**: 20 problems resumed from a checkpoint instead of restarting (9, 84, 118, 119, 169, 174, 190, 217, 219, 231, 233, 263, 268, 330, 440, 446, 485, 509, 780, 801).
- **Cycles taken**: 19 spec revisions (write_spec ↺ check/critic), 132 proof repairs (verify ↺ repair), 1 safety fallbacks.
- **Human-in-the-loop**: 0 specs went through `interrupt()` review.
- **LLM cache hits**: 1 of 252 calls.

## Specs for human review

Every proof is only as good as its spec. Review these (critic verdicts and example checks are automated hints, not proof).

<details><summary><b>42. Trapping Rain Water</b> — verified — examples pre 2/2, post 2/2, wrong outputs rejected 4/4</summary>

```rust
spec fn max_int(a: int, b: int) -> int {
    if a >= b { a } else { b }
}

spec fn min_int(a: int, b: int) -> int {
    if a <= b { a } else { b }
}

spec fn seq_max(s: Seq<i32>) -> int
    decreases s.len()
{
    if s.len() == 0 {
        0
    } else if s.len() == 1 {
        s[0] as int
    } else {
        max_int(s[0] as int, seq_max(s.skip(1)))
    }
}

spec fn water_at(s: Seq<i32>, i: int) -> int {
    if 0 <= i < s.len() {
        min_int(
            seq_max(s.take(i + 1)),
            seq_max(s.skip(i)),
        ) - s[i] as int
    } else {
        0
    }
}

spec fn total_water(s: Seq<i32>, n: int) -> int
    decreases n
{
    if n <= 0 {
        0
    } else {
        total_water(s, n - 1) + water_at(s, n - 1)
    }
}

spec fn pre(height: Seq<i32>) -> bool {
    1 <= height.len() <= 20000
    && forall|i: int| 0 <= i < height.len() ==> #[trigger] height[i] >= 0 && height[i] <= 100000
}

spec fn post(height: Seq<i32>, result: i32) -> bool {
    result as int == total_water(height, height.len() as int)
}
```

</details>

<details><summary><b>84. Largest Rectangle in Histogram</b> — verified — examples pre 2/2, post 2/2, wrong outputs rejected 4/4</summary>

```rust
spec fn max_int(a: int, b: int) -> int {
    if a >= b { a } else { b }
}

spec fn min_int(a: int, b: int) -> int {
    if a <= b { a } else { b }
}

spec fn height_val(s: Seq<i32>, i: int) -> int {
    if 0 <= i && i < s.len() {
        s[i] as int
    } else {
        0
    }
}

spec fn min_range(s: Seq<i32>, lo: int, hi: int) -> int
    decreases hi - lo
{
    if lo >= hi {
        0
    } else if lo + 1 == hi {
        height_val(s, lo)
    } else {
        min_int(height_val(s, lo), min_range(s, lo + 1, hi))
    }
}

spec fn max_area_ending_at(s: Seq<i32>, lo: int, end: int) -> int
    decreases end - lo + 1
{
    if lo > end {
        0
    } else {
        max_int(
            (end - lo + 1) * min_range(s, lo, end + 1),
            max_area_ending_at(s, lo + 1, end)
        )
    }
}

spec fn max_area_prefix(s: Seq<i32>, len: int) -> int
    decreases len
{
    if len <= 0 {
        0
    } else {
        max_int(
            max_area_prefix(s, len - 1),
            max_area_ending_at(s, 0, len - 1)
        )
    }
}

spec fn largest_rect_area(s: Seq<i32>) -> int {
    max_area_prefix(s, s.len() as int)
}

spec fn pre(heights: Seq<i32>) -> bool {
    &&& 1 <= heights.len() as int
    &&& heights.len() as int <= 100000
    &&& (forall|i: int|
            0 <= i < heights.len() ==>
                0 <= #[trigger] heights[i] && heights[i] <= 10000)
}

spec fn post(heights: Seq<i32>, result: i32) -> bool {
    result as int == largest_rect_area(heights)
}
```

</details>

<details><summary><b>169. Majority Element</b> — verified — examples pre 2/2, post 2/2, wrong outputs rejected 4/4</summary>

```rust
spec fn count(s: Seq<i32>, x: i32) -> int
    decreases s.len()
{
    if s.len() == 0 {
        0int
    } else {
        count(s.drop_last(), x) + (if s.last() == x { 1int } else { 0int })
    }
}

spec fn pre(nums: Seq<i32>) -> bool
{
    1int <= nums.len() as int &&
    nums.len() as int <= 50000int &&
    (forall|i: int|
        0int <= i < nums.len() as int ==>
            -1000000000int <= nums[i] as int &&
            nums[i] as int <= 1000000000int) &&
    (exists|i: int|
        0int <= i < nums.len() as int &&
        count(nums, nums[i]) > nums.len() as int / 2int)
}

spec fn post(nums: Seq<i32>, result: i32) -> bool
{
    count(nums, result) > nums.len() as int / 2int
}
```

</details>

<details><summary><b>217. Contains Duplicate</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 3/3</summary>

```rust
spec fn value_in_bounds(x: i32) -> bool {
    -1000000000 <= (x as int) && (x as int) <= 1000000000
}

spec fn has_duplicate(nums: Seq<i32>) -> bool {
    exists|i: int, j: int|
        0 <= i && i < j && j < (nums.len() as int)
            && nums[i] == nums[j]
}

spec fn pre(nums: Seq<i32>) -> bool {
    1 <= (nums.len() as int)
        && (nums.len() as int) <= 100000
        && forall|i: int|
            0 <= i && i < (nums.len() as int)
                ==> #[trigger] value_in_bounds(nums[i])
}

spec fn post(nums: Seq<i32>, result: bool) -> bool {
    result <==> has_duplicate(nums)
}
```

</details>

<details><summary><b>231. Power of Two</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 3/3</summary>

```rust
spec fn pow2(e: nat) -> int
    decreases e
{
    if e == 0 {
        1
    } else {
        2 * pow2((e - 1) as nat)
    }
}

spec fn pre(n: i32) -> bool {
    -2147483648 <= n as int && n as int <= 2147483647
}

spec fn post(n: i32, result: bool) -> bool {
    result <==> exists|e: nat| e < 31 && pow2(e) == n as int
}
```

</details>

<details><summary><b>233. Number of Digit One</b> — verified — examples pre 2/2, post 2/2, wrong outputs rejected 4/4</summary>

```rust
// Counts how many times digit 1 appears at decimal position `p`
// among all numbers 0..n, assuming p is a positive power of 10.
spec fn count_at_position(n: int, p: int) -> int {
    if p <= 0 {
        0
    } else {
        let cycle = 10 * p;
        let full = (n / cycle) * p;
        let r = n % cycle;
        let extra = if r < p {
            0
        } else if r - p + 1 < p {
            r - p + 1
        } else {
            p
        };
        full + extra
    }
}

// Total number of digit 1 occurrences in all non-negative integers <= n,
// for n <= 10^9.  We sum over all possible decimal positions.
spec fn total_ones_upto(n: int) -> int {
    count_at_position(n, 1)
    + count_at_position(n, 10)
    + count_at_position(n, 100)
    + count_at_position(n, 1000)
    + count_at_position(n, 10000)
    + count_at_position(n, 100000)
    + count_at_position(n, 1000000)
    + count_at_position(n, 10000000)
    + count_at_position(n, 100000000)
    + count_at_position(n, 1000000000)
}

spec fn pre(n: i32) -> bool {
    0 <= n as int && n as int <= 1000000000
}

spec fn post(n: i32, result: i32) -> bool {
    result as int == total_ones_upto(n as int)
}
```

</details>

<details><summary><b>263. Ugly Number</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 3/3</summary>

```rust
spec fn is_ugly_rec(n: int) -> bool
    recommends 0 <= n
    decreases n
{
    if n <= 0 {
        false
    } else if n == 1 {
        true
    } else if n % 2 == 0 {
        is_ugly_rec(n / 2)
    } else if n % 3 == 0 {
        is_ugly_rec(n / 3)
    } else if n % 5 == 0 {
        is_ugly_rec(n / 5)
    } else {
        false
    }
}

spec fn is_ugly_number(n: int) -> bool
{
    if n <= 0 {
        false
    } else {
        is_ugly_rec(n)
    }
}

spec fn pre(num: i32) -> bool
{
    -2147483648 <= num as int && num as int <= 2147483647
}

spec fn post(num: i32, result: bool) -> bool
{
    result <==> is_ugly_number(num as int)
}
```

</details>

<details><summary><b>268. Missing Number</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 6/6</summary>

```rust
spec fn contains_int(nums: Seq<i32>, x: int) -> bool
    decreases nums.len(),
{
    if nums.len() == 0 {
        false
    } else {
        (nums.last() as int) == x || contains_int(nums.drop_last(), x)
    }
}

spec fn pre(nums: Seq<i32>) -> bool {
    let n = nums.len() as int;
    1 <= n && n <= 10000
        && (forall|i: int| 0 <= i < nums.len() ==> 0 <= (nums[i] as int) && (nums[i] as int) <= n)
        && (forall|i: int, j: int| 0 <= i < j < nums.len() ==> nums[i] != nums[j])
}

spec fn post(nums: Seq<i32>, result: i32) -> bool {
    let n = nums.len() as int;
    let r = result as int;
    0 <= r && r <= n
        && !contains_int(nums, r)
        && (forall|x: int| 0 <= x && x <= n && x != r ==> contains_int(nums, x))
}
```

</details>

<details><summary><b>292. Nim Game</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 3/3</summary>

```rust
spec fn pre(n: i32) -> bool {
    1 <= (n as int) && (n as int) <= 2147483647
}

spec fn post(n: i32, result: bool) -> bool {
    result == (((n as int) % 4) != 0)
}
```

</details>

<details><summary><b>342. Power of Four</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 3/3</summary>

```rust
spec fn is_power_of_four_depth(n: int, k: int) -> bool
    decreases k
{
    if k <= 0 {
        n == 1
    } else if n <= 0 {
        false
    } else if n == 1 {
        true
    } else if n % 4 != 0 {
        false
    } else {
        is_power_of_four_depth(n / 4, k - 1)
    }
}

spec fn is_power_of_four_spec(n: int) -> bool {
    is_power_of_four_depth(n, 15)
}

spec fn pre(n: i32) -> bool {
    (-2147483648) <= (n as int) && (n as int) <= 2147483647
}

spec fn post(n: i32, result: bool) -> bool {
    result <==> is_power_of_four_spec(n as int)
}
```

</details>

<details><summary><b>485. Max Consecutive Ones</b> — verified — examples pre 2/2, post 2/2, wrong outputs rejected 4/4</summary>

```rust
spec fn initial_run_len(s: Seq<i32>) -> int
    decreases s.len()
{
    if s.len() == 0 {
        0
    } else {
        if s[0] == 0 {
            0
        } else {
            1 + initial_run_len(s.skip(1))
        }
    }
}

spec fn max_consecutive_ones(s: Seq<i32>) -> int
    decreases s.len()
{
    if s.len() == 0 {
        0
    } else {
        let current_run = initial_run_len(s);
        let rest_run = max_consecutive_ones(s.skip(1));
        if current_run >= rest_run {
            current_run
        } else {
            rest_run
        }
    }
}

spec fn pre(nums: Seq<i32>) -> bool {
    nums.len() >= 1 && nums.len() <= 100000
        && (forall|i: int| 0 <= i < nums.len() ==> nums[i] == 0 || nums[i] == 1)
}

spec fn post(nums: Seq<i32>, result: i32) -> bool {
    result as int == max_consecutive_ones(nums)
}
```

</details>

<details><summary><b>509. Fibonacci Number</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 6/6</summary>

```rust
spec fn fibonacci(n: int) -> int
    decreases n
{
    if n <= 1 {
        n
    } else {
        fibonacci(n - 1) + fibonacci(n - 2)
    }
}

spec fn pre(n: i32) -> bool {
    0 <= n && n <= 30
}

spec fn post(n: i32, result: i32) -> bool {
    result as int == fibonacci(n as int)
}
```

</details>

<details><summary><b>780. Reaching Points</b> — verified — examples pre 3/3, post 3/3, wrong outputs rejected 3/3</summary>

```rust
spec fn reach_fuel(sx: int, sy: int, tx: int, ty: int, fuel: nat) -> bool
    decreases fuel
{
    if sx <= 0 || sy <= 0 {
        false
    } else if tx == sx && ty == sy {
        true
    } else if tx < sx || ty < sy {
        false
    } else if fuel == 0 {
        false
    } else if sx < tx && sy < ty {
        if tx < ty {
            reach_fuel(sx, sy, tx, ty % tx, (fuel - 1) as nat)
        } else {
            reach_fuel(sx, sy, tx % ty, ty, (fuel - 1) as nat)
        }
    } else {
        (tx == sx && ty >= sy && (ty - sy) % sx == 0) ||
        (ty == sy && tx >= sx && (tx - sx) % sy == 0)
    }
}

spec fn pre(sx: i32, sy: i32, tx: i32, ty: i32) -> bool {
    1 <= sx as int && sx as int <= 1000000000 &&
    1 <= sy as int && sy as int <= 1000000000 &&
    1 <= tx as int && tx as int <= 1000000000 &&
    1 <= ty as int && ty as int <= 1000000000
}

spec fn post(sx: i32, sy: i32, tx: i32, ty: i32, result: bool) -> bool {
    if pre(sx, sy, tx, ty) {
        result == reach_fuel(
            sx as int,
            sy as int,
            tx as int,
            ty as int,
            ((tx as int) + (ty as int)) as nat,
        )
    } else {
        true
    }
}
```

</details>
