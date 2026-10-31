"""lcverus command line.

  lcverus scan                       shape statistics over all rustgym solutions
  lcverus select --pilot 30          pick N Easy, free, Verus-parsable problems -> data/pilot.json
  lcverus select --pilot 20 --difficulty Hard --set hard   -> data/hard.json
  lcverus run --pilot [--set hard] | --ids 1,26   run the LangGraph pipeline (resumes unfinished threads)
  lcverus review PID [--approve | --reject TEXT | --edit FILE]
  lcverus status PID                 state, pending node and event timeline of one thread
  lcverus rewind PID NODE            time-travel: re-run from the last checkpoint before NODE
  lcverus report                     write reports/summary.md
  lcverus graph                      write reports/graph.md (Mermaid)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

from langgraph.types import Command

from . import report
from .config import load
from .nodes.intake import analyze
from .sources import leetcode, rustgym
from .state import is_final, run_dir
from . import verus


def _sources() -> dict[int, rustgym.Source]:
    return rustgym.scan(load().path("rustgym"))


def cmd_scan(args) -> None:
    srcs = _sources()
    allowed = set(load()["pilot"]["types"])
    c = Counter(":".join((rustgym.shape_issue(s, allowed) or "ok").split(":")[:2]) for s in srcs.values())
    print(f"{len(srcs)} solutions")
    for k, v in c.most_common(20):
        print(f"  {v:5d}  {k}")


def cmd_select(args) -> None:
    cfg = load()
    srcs = _sources()
    allowed = set(cfg["pilot"]["types"])
    diffs = set(args.difficulty.split(",")) if args.difficulty else set(cfg["pilot"]["difficulties"])
    chosen, skipped = [], Counter()
    for pid, s in sorted(srcs.items()):
        if len(chosen) >= args.pilot:
            break
        if rustgym.shape_issue(s, allowed):
            continue
        q = leetcode.fetch(pid)
        if not q or not q.get("content"):
            skipped["premium_or_missing"] += 1
            continue
        if q["difficulty"] not in diffs:
            skipped[f"difficulty:{q['difficulty']}"] += 1
            continue
        d = run_dir(pid)

        def write(name: str, text: str, d=d) -> Path:
            (d / name).write_text(text)
            return d / name

        res = analyze(Path(s.path), leetcode.parse_examples(q), verus.run, write)
        if res["status"] != "running":
            skipped[res["status"]] += 1
            print(f"  skip {pid:5d} {q['title'][:40]:40s} {res['status']}")
            continue
        chosen.append({"pid": pid, "path": s.path, "title": q["title"], "examples": len(res["examples"])})
        print(f"  pick {pid:5d} {q['title'][:40]:40s} ({len(res['examples'])} examples)")
    out = cfg.path("cache").parent / f"{args.set}.json"
    out.write_text(json.dumps({"chosen": chosen, "skipped": skipped}, indent=1))
    print(f"\n{len(chosen)} problems -> {out}\nskipped: {dict(skipped)}")


def _graph():
    from .graph import compile_graph
    return compile_graph()


def cmd_run(args) -> None:
    from .graph import thread_config
    cfg = load()
    graph = _graph()
    srcs = _sources()
    if args.ids:
        pids = [int(x) for x in args.ids.split(",")]
    else:
        pilot = json.loads((cfg.path("cache").parent / f"{args.set}.json").read_text())["chosen"]
        pids = [p["pid"] for p in pilot][: args.limit or None]

    inputs, configs, kinds = [], [], {}
    for pid in pids:
        if pid not in srcs:
            print(f"p{pid}: no rustgym solution")
            continue
        tc = thread_config(pid, args.tag)
        snap = graph.get_state(tc)
        if args.force and snap.values:
            graph.checkpointer.delete_thread(tc["configurable"]["thread_id"])
            shutil.rmtree(run_dir(pid), ignore_errors=True)
            snap = graph.get_state(tc)
        status = (snap.values or {}).get("status") or ""
        if args.retry_errors and not snap.next and status.startswith("error:"):
            node_name = status.split(":", 1)[1]
            target = next((h for h in graph.get_state_history(tc) if h.next == (node_name,)), None)
            if target is not None:
                print(f"p{pid}: retrying from {node_name} (was {status})")
                kinds[pid] = "retry"
                inputs.append(None)
                configs.append({**target.config, "recursion_limit": tc["recursion_limit"]})
                continue
        if snap.values and not snap.next and is_final(status):
            print(f"p{pid}: already finished ({status}); --force to rerun")
            continue
        if snap.next:
            if any(t.interrupts for t in snap.tasks):
                print(f"p{pid}: waiting for spec review (lcverus review {pid})")
                continue
            kinds[pid] = "resume"
            inputs.append(None)  # LangGraph resumes from the last checkpoint
            rp = run_dir(pid) / "resumes.json"
            hist = json.loads(rp.read_text()) if rp.exists() else []
            rp.write_text(json.dumps(hist + [{"t": time.time(), "next": list(snap.next)}]))
        else:
            kinds[pid] = "fresh"
            inputs.append({"pid": pid, "path": srcs[pid].path, "review_specs": args.review_specs, "events": []})
        configs.append(tc)
    if not configs:
        return
    started = {c["configurable"]["thread_id"] for c in configs}
    print(f"running {len(configs)} problems ({Counter(kinds.values())}), max_concurrency={cfg['graph']['max_concurrency']}")
    t0 = time.time()
    results = graph.batch(inputs, configs, max_concurrency=cfg["graph"]["max_concurrency"], return_exceptions=True)
    wall = time.time() - t0
    sum_node = 0.0
    for tc, res in zip(configs, results):
        tid = tc["configurable"]["thread_id"]
        if isinstance(res, Exception):
            print(f"{tid}: exception {type(res).__name__}: {res}")
            continue
        if "__interrupt__" in res:
            print(f"{tid}: paused for spec review -> lcverus review {res['pid']}")
        else:
            print(f"{tid}: {res.get('status')}")
        sum_node += sum(e["seconds"] for e in res.get("events", []) if e["t"] >= t0 - 1)
    (cfg.path("reports")).mkdir(parents=True, exist_ok=True)
    (cfg.path("reports") / "last_run.json").write_text(json.dumps(
        {"problems": len(started), "max_concurrency": cfg["graph"]["max_concurrency"], "wall_s": wall, "sum_node_s": sum_node}))
    report.build()
    print(f"\nreport: {cfg.path('reports') / 'summary.md'}")


def cmd_review(args) -> None:
    from .graph import thread_config
    graph = _graph()
    tc = thread_config(args.pid, args.tag)
    snap = graph.get_state(tc)
    pending = [i for t in snap.tasks for i in t.interrupts]
    if not pending:
        print("nothing to review for this problem")
        return
    payload = pending[0].value
    if not (args.approve or args.reject or args.edit):
        print(f"# {payload['pid']}. {payload['title']}\n\n{payload['spec_fns']}\n\ncritic: {json.dumps(payload['critic'], indent=1)}")
        for r in payload.get("examples") or []:
            print(f"  {r['kind']:4s} ex{r['example'] + 1}: {r['status']:8s} {r['assertion'][:100]}")
        print("\nre-run with --approve, --reject 'why', or --edit spec.rs")
        return
    if args.approve:
        decision = {"action": "approve"}
    elif args.reject:
        decision = {"action": "reject", "feedback": args.reject}
    else:
        decision = {"action": "edit", "spec_fns": Path(args.edit).read_text()}
    res = graph.invoke(Command(resume=decision), tc)
    print(res.get("status") if "__interrupt__" not in res else "paused for review again")
    report.build()


def cmd_rewind(args) -> None:
    """Fork a thread from its latest checkpoint before NODE (LangGraph time travel) and run from there."""
    from .graph import thread_config
    graph = _graph()
    tc = thread_config(args.pid, args.tag)
    target = next((h for h in graph.get_state_history(tc) if h.next == (args.node,)), None)
    if target is None:
        print(f"no checkpoint of p{args.pid} that is about to run {args.node}")
        return
    print(f"rewinding p{args.pid} to checkpoint {target.config['configurable']['checkpoint_id']} (next: {args.node})")
    res = graph.invoke(None, {**target.config, "recursion_limit": tc["recursion_limit"]})
    print(res.get("status"))
    report.build()


def cmd_status(args) -> None:
    from .graph import thread_config
    snap = _graph().get_state(thread_config(args.pid, args.tag))
    if not snap.values:
        print("no such thread")
        return
    v = snap.values
    print(f"status={v.get('status')} next={list(snap.next)} spec_round={v.get('spec_round')} "
          f"mode={v.get('mode')} proof_round={v.get('proof_round')}")
    for e in v.get("events", []):
        llm = sum(c["output_tokens"] for c in e.get("llm", []))
        res = e.get("result", {})
        print(f"  {e['node']:16s} {e['seconds']:7.1f}s  llm_out={llm:6d}  verus={len(e.get('verus', []))}  {res if res else ''}")


LLM_NODES = ["write_spec", "check_spec", "critic_spec", "prove", "repair", "find_counterexample", "safety_fallback"]


def cmd_handoff(args) -> None:
    """Write runs/p<id>/handoff.md: what the repair model would see, for an outside prover (e.g. a Claude Code agent)."""
    from .graph import thread_config
    from .nodes.proof import _context
    from .template import numbered
    graph = _graph()
    snap = graph.get_state(thread_config(args.pid, args.tag))
    v = snap.values or {}
    if not v.get("spec_hash"):
        sys.exit(f"p{args.pid}: no frozen spec yet (next={snap.next}); only proof work can be handed off")
    best = v.get("best") or {}
    base_file, base_fb = (best["file"], best["feedback"]) if best.get("file") else (v.get("last_file", ""), v.get("feedback", ""))
    prompts = Path(__file__).parent / "prompts"
    text = (
        f"# Handoff: p{args.pid}, mode {v.get('mode', 'functional')}, after round {v.get('proof_round', 0)}\n\n"
        f"Rules: {prompts / 'prover.md'} and {prompts / 'repair.md'}. Verus guide: {prompts / 'verus_guide.md'}.\n\n"
        + _context(v)
        + (f"\n## Best attempt so far (round {best.get('round')}, {best.get('errors')} errors)\n```rust\n{numbered(base_file)}\n```\n"
           f"\n## Verus / checker output for it\n```\n{base_fb}\n```\n" if base_file else "")
        + (f"\n## Latest attempt's output\n```\n{v.get('feedback', '')[:4000]}\n```\n" if v.get("feedback") and v.get("feedback") != base_fb else "")
    )
    out = run_dir(args.pid) / "handoff.md"
    out.write_text(text)
    print(out)


def cmd_submit(args) -> None:
    """Feed an outside attempt (<analysis>/<lemmas>/<body>) into the graph as a repair round, then run verify.

    Same integrity checker and Verus as any other round; the run stops before any DeepSeek node."""
    from .graph import thread_config
    from .nodes.proof import _parse
    graph = _graph()
    tc = thread_config(args.pid, args.tag)
    v = graph.get_state(tc).values or {}
    if not v.get("spec_hash"):
        sys.exit(f"p{args.pid}: no frozen spec yet")
    if is_final(v.get("status") or "") and v.get("status") != "running":
        sys.exit(f"p{args.pid}: already finished ({v['status']})")
    cand = _parse(Path(args.file).read_text())
    if cand["suspected_bug"]:
        sys.exit("bug claims go through `lcverus run` (the judge is a DeepSeek call); put the reasoning in <analysis>")
    rnd = v.get("proof_round", 0) + 1
    ev = {"node": "repair", "t": round(time.time(), 1), "seconds": 0.0, "llm": [], "verus": [], "spec_round": v.get("spec_round", 0),
          "proof_round": rnd, "mode": v.get("mode"), "external": args.by}
    graph.update_state(tc, {"candidate": cand, "proof_round": rnd, "events": [ev]}, as_node="repair")
    graph.invoke(None, tc, interrupt_before=LLM_NODES)
    snap = graph.get_state(tc)
    s = snap.values
    print(f"p{args.pid} round {rnd}: status={s.get('status')} next={snap.next} last_ok={s.get('last_ok')}")
    if not s.get("last_ok"):
        print(s.get("feedback", "")[:6000])


def cmd_report(args) -> None:
    report.build()
    print(load().path("reports") / "summary.md")


def cmd_graph(args) -> None:
    from .graph import build
    from langgraph.checkpoint.memory import InMemorySaver
    mm = build().compile(checkpointer=InMemorySaver()).get_graph().draw_mermaid()
    out = load().path("reports") / "graph.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("# lcverus pipeline (LangGraph)\n\n```mermaid\n" + mm + "\n```\n")
    print(out)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lcverus", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(fn=cmd_scan)
    p = sub.add_parser("select")
    p.add_argument("--pilot", type=int, default=30)
    p.add_argument("--difficulty", help="comma list, e.g. Hard (default: config pilot.difficulties)")
    p.add_argument("--set", default="pilot", help="problem set name -> data/<set>.json")
    p.set_defaults(fn=cmd_select)
    p = sub.add_parser("run")
    p.add_argument("--ids")
    p.add_argument("--pilot", action="store_true", help="run the problems in data/<set>.json")
    p.add_argument("--set", default="pilot", help="problem set name (data/<set>.json)")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--review-specs", action="store_true", help="pause for human approval of each spec")
    p.add_argument("--force", action="store_true", help="discard previous checkpoints and rerun")
    p.add_argument("--retry-errors", action="store_true", help="re-run problems that ended in error:<node> from that node")
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("review")
    p.add_argument("pid", type=int)
    p.add_argument("--approve", action="store_true")
    p.add_argument("--reject")
    p.add_argument("--edit")
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_review)
    p = sub.add_parser("rewind", help="re-run a problem from its last checkpoint before NODE")
    p.add_argument("pid", type=int)
    p.add_argument("node")
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_rewind)
    p = sub.add_parser("status")
    p.add_argument("pid", type=int)
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("handoff", help="write runs/p<id>/handoff.md for an outside prover")
    p.add_argument("pid", type=int)
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_handoff)
    p = sub.add_parser("submit", help="verify an outside attempt as the next repair round")
    p.add_argument("pid", type=int)
    p.add_argument("file", help="text with <analysis>, <lemmas> and <body> sections")
    p.add_argument("--by", default="external", help="who wrote it (recorded in the event log)")
    p.add_argument("--tag", default="")
    p.set_defaults(fn=cmd_submit)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    sub.add_parser("graph").set_defaults(fn=cmd_graph)
    args = ap.parse_args(argv)
    if args.cmd == "run" and not (args.ids or args.pilot):
        ap.error("run needs --ids or --pilot")
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
