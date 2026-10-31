"""End-to-end graph runs with the LLM stubbed out (real Verus). Slow: ~1 minute."""

import json
import shutil
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from lcverus import llm
from lcverus.config import load
from lcverus.graph import compile_graph, thread_config
from lcverus.sources import leetcode

FIX = Path(__file__).resolve().parent.parent / "fixtures"
SRC = FIX / "src/d90/_9001_array_total.rs"

SPEC = """spec fn sum(s: Seq<i32>) -> int
    decreases s.len(),
{
    if s.len() == 0 { 0 } else { sum(s.drop_last()) + s.last() as int }
}
spec fn pre(a: Seq<i32>) -> bool {
    1 <= a.len() <= 1000 && forall|i: int| 0 <= i < a.len() ==> -1000 <= #[trigger] a[i] <= 1000
}
spec fn post(a: Seq<i32>, result: i32) -> bool {
    result as int == sum(a)
}"""

LEMMAS = """proof fn lemma_sum_bounds(s: Seq<i32>)
    requires forall|i: int| 0 <= i < s.len() ==> -1000 <= #[trigger] s[i] <= 1000,
    ensures -1000 * s.len() <= sum(s) <= 1000 * s.len(),
    decreases s.len(),
{
    if s.len() > 0 {
        lemma_sum_bounds(s.drop_last());
    }
}"""

BODY = """{
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
}"""


def _proof_reply(body):
    return f"<lemmas>\n```rust\n{LEMMAS}\n```\n</lemmas>\n<body>\n```rust\n{body}\n```\n</body>"


@pytest.fixture
def stub(tmp_path, monkeypatch):
    cfg = load()
    monkeypatch.setitem(cfg.raw, "paths", {**cfg.raw["paths"], "runs": str(tmp_path / "runs"), "cache": str(tmp_path / "cache")})
    monkeypatch.setitem(cfg.raw, "budgets", {"spec_rounds": 2, "proof_rounds": 2, "safety_rounds": 1, "example_hint_tries": 1})
    q = json.loads((FIX / "q9001.json").read_text())
    monkeypatch.setattr(leetcode, "fetch", lambda pid: q)
    replies = {}

    def fake_chat(role, system, user, *, sample=0, use_cache=True, required_tags=()):
        text = replies[role]
        return llm.Reply(text, "stub", role, len(user) // 4, len(text) // 4, 0.0, False)

    monkeypatch.setattr(llm, "chat", fake_chat)
    replies["spec_writer"] = f"<spec_fns>\n```rust\n{SPEC}\n```\n</spec_fns><notes>-</notes>"
    replies["critic"] = '<verdict>{"verdict": "accept", "confidence": 0.9, "issues": []}</verdict>'
    replies["example_prover"] = "<false>stub</false>"
    return replies, tmp_path


def _run(tmp_path):
    g = compile_graph(InMemorySaver())
    path = tmp_path / "_9001_array_total.rs"
    shutil.copy(SRC, path)
    return g.invoke({"pid": 9001, "path": str(path), "events": []}, thread_config(9001))


@pytest.mark.slow
def test_honest_proof_verifies(stub):
    replies, tmp = stub
    replies["prover"] = replies["repair"] = _proof_reply(BODY)
    out = _run(tmp)
    assert out["status"] == "verified", out.get("reason") or out.get("feedback")
    kinds = {(r["kind"], r["status"]) for r in out["example_results"]}
    assert kinds == {("pre", "proved"), ("post", "proved"), ("neg", "proved")}
    assert out["runtime"]["orig_tests"] == "pass"
    assert all(e["match"] for e in out["runtime"]["examples"])
    assert (tmp / "runs/p9001/final.rs").exists()


@pytest.mark.slow
def test_cheating_prover_is_caught(stub):
    replies, tmp = stub
    cheat = BODY.replace("proof {", "proof {\n            assume(false);")
    replies["prover"] = replies["repair"] = _proof_reply(cheat)
    out = _run(tmp)
    assert out["status"] == "proof_failed:guard_violation"
    assert not (tmp / "runs/p9001/final.rs").exists()


@pytest.mark.slow
def test_wrong_spec_is_caught_by_examples(stub):
    replies, tmp = stub
    wrong = SPEC.replace("result as int == sum(a)", "result as int == sum(a) + 1")
    replies["spec_writer"] = f"<spec_fns>\n```rust\n{wrong}\n```\n</spec_fns>"
    replies["prover"] = replies["repair"] = _proof_reply(BODY)
    out = _run(tmp)
    assert out["status"] == "spec_rejected"
    post = [r for r in out["example_results"] if r["kind"] == "post"]
    assert post and all(r["status"] == "refuted" for r in post)
