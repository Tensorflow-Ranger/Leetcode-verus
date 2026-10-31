"""The LangGraph state machine. One thread (= checkpoint history) per problem."""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .config import load
from .nodes.finish import finalize, runtime
from .nodes.intake import fetch, triage
from .nodes.bug import find_counterexample, route_after_cex
from .nodes.proof import prove, repair, route_after_repair, route_after_verify, safety_fallback, verify
from .nodes.spec import check_spec, critic_spec, human_review, write_spec
from .state import ProblemState


def _spec_budget_left(s: ProblemState) -> bool:
    return s.get("spec_round", 0) < load()["budgets"]["spec_rounds"]


def route_running(s: ProblemState) -> str:
    return "continue" if s.get("status") == "running" else "finalize"


def route_after_write(s: ProblemState) -> str:
    if s.get("status", "running") != "running":
        return "finalize"
    if s.get("spec_fns"):
        return "check_spec"
    return "write_spec" if _spec_budget_left(s) else "finalize"


def route_after_check(s: ProblemState) -> str:
    if not s.get("spec_feedback"):
        return "critic_spec"
    refuted = any(r["kind"] in ("pre", "post") and r["status"] == "refuted" for r in s.get("example_results", []))
    if s.get("example_results") and not refuted and not _spec_budget_left(s):
        return "critic_spec"  # examples unconfirmed (not refuted) on the last round: let the critic weigh in
    return "write_spec" if _spec_budget_left(s) else "finalize"


def route_after_critic(s: ProblemState) -> str:
    if s["critic"]["verdict"] == "accept":
        return "human_review" if s.get("review_specs") else "prove"
    return "write_spec" if _spec_budget_left(s) else "finalize"


def route_after_review(s: ProblemState) -> str:
    action = s["review"]["action"]
    if action == "approve":
        return "prove"
    if action == "edit":
        return "check_spec"
    return "write_spec" if _spec_budget_left(s) else "finalize"


def build() -> StateGraph:
    g = StateGraph(ProblemState)
    for name, fn in [
        ("fetch", fetch), ("triage", triage),
        ("write_spec", write_spec), ("check_spec", check_spec), ("critic_spec", critic_spec), ("human_review", human_review),
        ("prove", prove), ("verify", verify), ("repair", repair), ("safety_fallback", safety_fallback), ("find_counterexample", find_counterexample),
        ("runtime", runtime), ("finalize", finalize),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "fetch")
    g.add_conditional_edges("fetch", route_running, {"continue": "triage", "finalize": "finalize"})
    g.add_conditional_edges("triage", route_running, {"continue": "write_spec", "finalize": "finalize"})
    g.add_conditional_edges("write_spec", route_after_write, ["check_spec", "write_spec", "finalize"])
    g.add_conditional_edges("check_spec", route_after_check, ["critic_spec", "write_spec", "finalize"])
    g.add_conditional_edges("critic_spec", route_after_critic, ["human_review", "prove", "write_spec", "finalize"])
    g.add_conditional_edges("human_review", route_after_review, ["prove", "check_spec", "write_spec", "finalize"])
    g.add_edge("prove", "verify")
    g.add_conditional_edges("verify", route_after_verify, ["runtime", "repair", "find_counterexample", "safety_fallback", "finalize"])
    g.add_conditional_edges("repair", route_after_repair, ["verify", "find_counterexample"])
    g.add_conditional_edges("find_counterexample", route_after_cex, ["finalize", "safety_fallback", "write_spec", "repair"])
    g.add_edge("safety_fallback", "verify")
    g.add_edge("runtime", "finalize")
    g.add_edge("finalize", END)
    return g


def compile_graph(checkpointer=None):
    if checkpointer is None:
        path = load().path("checkpoints")
        path.parent.mkdir(parents=True, exist_ok=True)
        checkpointer = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    return build().compile(checkpointer=checkpointer)


def thread_config(pid: int, tag: str = "") -> dict:
    return {"configurable": {"thread_id": f"p{pid}{'-' + tag if tag else ''}"},
            "recursion_limit": load()["graph"]["recursion_limit"]}
