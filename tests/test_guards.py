"""The integrity checker must accept honest annotations and reject every cheat."""

from lcverus import guards
from lcverus.rustlex import erase, find_fns, texts, tokenize

ORIG = """{
    let mut s = 0;
    let mut i = 0;
    while i < a.len() {
        s += a[i];
        i += 1;
    }
    s
}"""

HONEST = """{
    let mut s = 0;
    let mut i = 0;
    let ghost n = a@.len();
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
        assert(s < 1000000) by { lemma_x(); }
        assert(i * 2 >= i) by (nonlinear_arith) requires i >= 0 { }
        assert forall|j: int| 0 <= j < i implies a@[j] == a@[j] by { }
        s += a[i];
        i += 1;
    }
    assert(a@.subrange(0, a.len() as int) =~= a@);
    s
}"""

LEMMAS = """proof fn lemma_sum_bounds(s: Seq<i32>)
    requires forall|i: int| 0 <= i < s.len() ==> -1000 <= #[trigger] s[i] <= 1000,
    ensures -1000 * s.len() <= sum(s) <= 1000 * s.len(),
    decreases s.len(),
{
    if s.len() > 0 { lemma_sum_bounds(s.drop_last()); }
}
spec fn helper(x: int) -> int { x + 1 }
"""


def test_honest_annotations_pass():
    assert guards.check_candidate(LEMMAS, HONEST, ORIG) == []


def test_erase_roundtrip():
    assert texts(erase(tokenize(HONEST))) == texts(tokenize(ORIG))


def test_changed_loop_bound_rejected():
    bad = HONEST.replace("while i < a.len()", "while i < a.len() - 1")
    errs = guards.check_body(bad, ORIG)
    assert errs and "differs from the original" in errs[0]


def test_dropped_statement_rejected():
    assert guards.check_body(HONEST.replace("i += 1;\n    }", "}"), ORIG)


def test_assume_rejected():
    bad = HONEST.replace("proof {", "proof {\n assume(false);")
    assert any("assume" in e for e in guards.check_body(bad, ORIG))


def test_admit_in_lemma_rejected():
    assert any("admit" in e for e in guards.check_items(LEMMAS.replace("if s.len()", "admit(); if s.len()"), "lemmas", True))


def test_external_body_rejected():
    bad = "#[verifier::external_body]\nproof fn lemma_false() ensures false { }\n"
    assert guards.check_items(bad, "lemmas", True)


def test_bodiless_axiom_rejected():
    assert any("axiom" in e for e in guards.check_items("proof fn ax() ensures false;\n", "lemmas", True))


def test_exec_fn_in_lemmas_rejected():
    assert any("exec fn" in e for e in guards.check_items("fn sneaky() -> u32 { 0 }\n", "lemmas", True))


def test_ghost_code_cannot_hide_exec_change():
    # exec code moved inside a proof block would be erased -> must show up as a mismatch
    bad = HONEST.replace("s += a[i];", "proof { }")
    assert guards.check_body(bad, ORIG)


def test_spec_needs_pre_and_post():
    assert guards.check_spec("spec fn pre(a: Seq<i32>) -> bool { true }")
    assert guards.check_spec("spec fn pre(a: Seq<i32>) -> bool { true }\nspec fn post(a: Seq<i32>, result: i32) -> bool { true }") == []
    assert guards.check_spec("uninterp spec fn pre(a: Seq<i32>) -> bool;\nspec fn post(a: Seq<i32>, result: i32) -> bool { true }")


def test_spec_hash_ignores_whitespace_and_comments():
    a = "spec fn pre(a: Seq<i32>) -> bool { true }"
    assert guards.spec_hash(a) == guards.spec_hash("// c\nspec fn pre(a: Seq<i32>)\n -> bool {\n true }")
    assert guards.spec_hash(a) != guards.spec_hash(a.replace("true", "false"))


def test_find_fns_signature():
    src = "impl Solution {\n    fn two(nums: Vec<i32>, mut k: i32) -> Vec<Vec<i32>> { vec![] }\n}"
    f = find_fns(src)[0]
    assert f.name == "two" and f.params == [("nums", "Vec<i32>", False), ("k", "i32", True)]
    assert f.ret == "Vec<Vec<i32>>" and f.body == "{ vec![] }"


def test_lexer_ranges_and_chars():
    assert texts(tokenize("for i in 0..n { x = 'a'; y = 1.5; }")) == [
        "for", "i", "in", "0", "..", "n", "{", "x", "=", "'a'", ";", "y", "=", "1.5", ";", "}"]
    assert texts(tokenize("'outer: loop { break 'outer; }"))[0] == "'outer"


def test_for_each_iterator_name_erased():
    orig = "{ let mut c = 0; for x in nums { if x == 1 { c += 1; } } c }"
    ann = """{ let mut c = 0;
        for x in it: nums
            invariant it.seq() == nums@, c == cnt(nums@.take(it.index())),
        { assert(nums@.take(it.index() + 1).drop_last() =~= nums@.take(it.index())); if x == 1 { c += 1; } }
        c }"""
    assert guards.check_body(ann, orig) == []
    assert guards.check_body(ann.replace("it: nums", "it: nums2"), orig)


def test_braces_inside_ensures():
    lem = """proof fn l(s: Seq<i32>)
    ensures f(s) == if g(s) { s.len() + 1 } else { f(s) },
    decreases s.len(),
{
    if s.len() == 0 { } else { l(s.skip(1)); }
}
spec fn h(x: int) -> int { if x > 0 { x } else { 0 } }
"""
    assert guards.check_items(lem, "lemmas", True) == []
    assert guards.check_items(lem + "proof fn ax() ensures if true { false } else { false };\n", "lemmas", True)
