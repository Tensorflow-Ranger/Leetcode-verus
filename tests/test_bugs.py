"""Counterexample search on planted bugs, with the LLM stubbed (real Verus + rustc). Slow."""

import json
import shutil
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from lcverus import llm
from lcverus.config import load
from lcverus.graph import compile_graph, thread_config
from lcverus.sources import leetcode

from test_pipeline import BODY, LEMMAS, SPEC

FIX = Path(__file__).resolve().parent.parent / "fixtures"
SPEC_BIG = SPEC.replace("-1000 <= #[trigger] a[i] <= 1000", "-1000000000 <= #[trigger] a[i] <= 1000000000")
BUGGY_BODY = BODY.replace("while i < a.len()", "while i + 1 < a.len()")


def _reply_body(body, lemmas=LEMMAS):
    return f"<lemmas>\n```rust\n{lemmas}\n```\n</lemmas>\n<body>\n```rust\n{body}\n```\n</body>"


@pytest.fixture
def env(tmp_path, monkeypatch):
    cfg = load()
    monkeypatch.setitem(cfg.raw, "paths", {**cfg.raw["paths"], "runs": str(tmp_path / "runs"), "cache": str(tmp_path / "cache")})
    monkeypatch.setitem(cfg.raw, "budgets", {"spec_rounds": 1, "proof_rounds": 1, "safety_rounds": 1, "example_hint_tries": 1})
    qs = {pid: json.loads((FIX / f"q{pid}.json").read_text()) for pid in (9001, 9002, 9003)}
    monkeypatch.setattr(leetcode, "fetch", lambda pid: qs[pid])
    script = {"calls": []}

    def fake_chat(role, system, user, *, sample=0, use_cache=True, required_tags=()):
        script["calls"].append(role)
        r = script[role]
        text = r(user) if callable(r) else r
        return llm.Reply(text, "stub", role, 1, 1, 0.0, False)

    monkeypatch.setattr(llm, "chat", fake_chat)
    script["critic"] = '<verdict>{"verdict": "accept", "confidence": 0.9, "issues": []}</verdict>'
    script["example_prover"] = "<false>stub</false>"
    return script, tmp_path


def _run(tmp, pid, name):
    path = tmp / name
    shutil.copy(FIX / "src/d90" / name, path)
    return compile_graph(InMemorySaver()).invoke({"pid": pid, "path": str(path), "events": []}, thread_config(pid))


def _judge(answer, valid=True, violated=None):
    return ('<verdict>' + json.dumps({"valid": valid, "violated_constraint": violated, "answer": answer,
                                      "reasoning": "stub"}) + '</verdict>')


@pytest.mark.slow
def test_wrong_answer_bug_is_found_and_validated(env):
    script, tmp = env
    script["spec_writer"] = f"<spec_fns>\n```rust\n{SPEC}\n```\n</spec_fns>"
    script["prover"] = script["repair"] = _reply_body(BUGGY_BODY)

    def judge(user):  # the judge computes the true sum from the input it is shown
        arr = json.loads(user.split("## Input to judge\na = ", 1)[1].split("\n")[0])
        return _judge(sum(arr))

    script["judge"] = judge
    out = _run(tmp, 9002, "_9002_array_total_skips_last.rs")
    assert out["status"] == "bug:wrong_answer", out.get("cex")
    cex = out["cex"]
    assert cex["judge_answer"] != cex["outcome"]
    assert any("!post" in e for e in cex["evidence"]) and any("post(X" in e for e in cex["evidence"])
    # the proof loop stopped: no further functional repair after the bug was confirmed
    nodes = [e["node"] for e in out["events"]]
    assert "repair" not in nodes[nodes.index("find_counterexample"):] or out["mode"] == "safety"
    assert (tmp / "runs/p9002/cex_harness.rs").exists()


@pytest.mark.slow
def test_overflow_panic_is_found(env):
    script, tmp = env
    script["spec_writer"] = f"<spec_fns>\n```rust\n{SPEC_BIG}\n```\n</spec_fns>"
    script["prover"] = script["repair"] = _reply_body(BODY)  # the old bounds lemma no longer holds -> proof fails
    script["judge"] = _judge(None)
    out = _run(tmp, 9003, "_9003_array_total_big.rs")
    assert out["status"] == "bug:panic", out.get("cex")
    assert "overflow" in out["cex"]["outcome"]


@pytest.mark.slow
def test_judge_disagreeing_on_validity_blames_the_spec_not_the_code(env):
    script, tmp = env
    script["spec_writer"] = f"<spec_fns>\n```rust\n{SPEC}\n```\n</spec_fns>"
    script["prover"] = script["repair"] = _reply_body(BUGGY_BODY)
    script["judge"] = _judge(None, valid=False, violated="1 <= a.length")
    out = _run(tmp, 9002, "_9002_array_total_skips_last.rs")
    assert out["status"] == "spec_suspect"
    assert not out["status"].startswith("bug")


@pytest.mark.slow
def test_false_bug_claim_is_checked_and_rejected(env):
    script, tmp = env
    load().raw["budgets"]["proof_rounds"] = 3  # room for: failed proof -> false claim -> real proof
    script["spec_writer"] = f"<spec_fns>\n```rust\n{SPEC}\n```\n</spec_fns>"
    script["prover"] = _reply_body(BODY.replace("decreases a.len() - i,", ""))  # fails: no decreases
    answers = iter(['<suspected_bug>{"inputs": [[1, 2, 3]], "why": "stub thinks the sum is off"}</suspected_bug>'])
    script["repair"] = lambda user: next(answers, _reply_body(BODY))
    script["judge"] = _judge(None)
    out = _run(tmp, 9001, "_9001_array_total.rs")
    assert out["cex"]["verdict"] == "none" and out["cex"]["trigger"] == "claim"
    assert out["status"] == "verified"  # the claim was refuted, the proof went on and succeeded
