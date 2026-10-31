import json
from pathlib import Path

from lcverus import template, verus
from lcverus.sources import leetcode

FIX = Path(__file__).resolve().parent.parent / "fixtures"

RAW = """error: invariant not satisfied at end of loop body
  --> /x/attempt.rs:31:17
   |
31 |                 s as int == sum(a@.subrange(0, i as int)),
   |                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

error: possible arithmetic underflow/overflow
  --> /x/attempt.rs:36:13
   |
36 |             s += a[i];
   |             ^^^^^^^^^

verification results:: 3 verified, 2 errors
error: aborting due to 2 previous errors
"""


def test_verus_parse():
    r = verus.parse(RAW, 1)
    assert not r.ok and r.verified == 3 and r.errors_count == 2
    assert [e.kind for e in r.errors] == ["invariant_end", "overflow"]
    assert [e.line for e in r.errors] == [31, 36]
    assert verus.errors_by_fn(r, {"a": (30, 32), "b": (33, 40)}) == {"a": [r.errors[0]], "b": [r.errors[1]]}


def test_verus_parse_ok():
    assert verus.parse("verification results:: 4 verified, 0 errors\n", 0).ok


def test_leetcode_examples_and_markdown():
    q = json.loads((FIX / "q121.json").read_text())
    assert leetcode.parse_examples(q) == [
        {"inputs": [[7, 1, 5, 3, 6, 4]], "output": 5, "raw_output": "5"},
        {"inputs": [[7, 6, 4, 3, 1]], "output": 0, "raw_output": "0"},
    ]
    md = leetcode.to_markdown(q)
    assert "10^5" in md and "Example 2" in md and "Constraints" in md  # <sup> preserved


def test_literals_and_mutations():
    assert template.spec_literal([1, -2], "Vec<i32>") == "seq![1i32, (-2i32)]"
    assert template.spec_literal([], "Vec<i32>") == "Seq::<i32>::empty()"
    assert template.spec_literal([[1], []], "Vec<Vec<i32>>") == "seq![seq![1i32], Seq::<i32>::empty()]"
    assert template.exec_literal([[1]], "Vec<Vec<i32>>") == "vec![vec![1i32]]"
    assert template.mutations(5, "i32") == [6, 4]
    assert template.mutations(True, "bool") == [False]
    assert template.mutations([0, 1], "Vec<i32>") == [[1, 1], [0], [0, 1, 1]]
    assert template.mutations(0, "usize") == [1]  # -1 does not fit usize


def test_section_strips_fences():
    from lcverus.llm import section
    assert section("<lemmas>\n```rust\n```\n</lemmas>", "lemmas") == ""
    assert section("<lemmas>```rust\n```</lemmas>", "lemmas") == ""
    assert section("<body>\n```rust\n{\n    x\n}\n```\n</body>", "body") == "{\n    x\n}"
    assert section("<b>plain</b>", "b") == "plain"
