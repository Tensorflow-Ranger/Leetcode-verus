"""reports/summary.md + summary.json from runs/p*/status.json and the checkpoint DB."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict

from .config import load
from .nodes.spec import spec_summary


def _load_runs() -> list[dict]:
    runs = []
    for p in sorted(load().path("runs").glob("p*/status.json"), key=lambda p: int(p.parent.name[1:].split("-")[0])):
        s = json.loads(p.read_text())
        rp = p.parent / "resumes.json"
        s["_resumes"] = json.loads(rp.read_text()) if rp.exists() else []
        runs.append(s)
    # problems stopped mid-run (Ctrl-C, budget guard) have no status.json yet: report them from their checkpoint
    from .graph import compile_graph, thread_config
    graph, done = compile_graph(), {r["pid"] for r in runs}
    for d in load().path("runs").glob("p*"):
        pid = d.name[1:]
        if not d.is_dir() or not pid.isdigit() or int(pid) in done:
            continue
        snap = graph.get_state(thread_config(int(pid)))
        if not snap.values or not snap.next:
            continue
        s = {k: v for k, v in snap.values.items() if k != "problem_md"}
        s["status"] = f"paused:{snap.next[0]}"
        rp = d / "resumes.json"
        s["_resumes"] = json.loads(rp.read_text()) if rp.exists() else []
        runs.append(s)
    runs.sort(key=lambda r: r["pid"])
    return runs


def _checkpoints() -> dict[str, int]:
    path = load().path("checkpoints")
    if not path.exists():
        return {}
    con = sqlite3.connect(path)
    try:
        rows = con.execute("select thread_id, count(*) from checkpoints group by thread_id").fetchall()
    except sqlite3.Error:
        rows = []
    con.close()
    return dict(rows)


def _frac(t) -> str:
    return f"{t[0]}/{t[1]}" if t[1] else "–"


def build() -> str:
    runs = _load_runs()
    from . import problem_report
    from .graph import compile_graph
    graph = compile_graph()
    for r in runs:
        try:
            problem_report.build(r["pid"], r, graph)
        except Exception as e:  # a broken write-up must not break the summary
            print(f"p{r['pid']}: problem report failed: {e}")
    cps = _checkpoints()
    out_dir = load().path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    statuses = Counter(r["status"].split(":")[0] for r in runs)
    detail = Counter(r["status"] for r in runs if r["status"].startswith(("unsupported", "shape", "fetch", "error")))

    node_agg: dict[str, dict] = defaultdict(lambda: Counter())
    for r in runs:
        for e in r.get("events", []):
            a = node_agg[e["node"]]
            a["calls"] += 1
            a["seconds"] += e["seconds"]
            for c in e.get("llm", []):
                a["llm_calls"] += 1
                a["llm_cached"] += c["cached"]
                a["tokens_in"] += c["input_tokens"]
                a["tokens_out"] += c["output_tokens"]
            for v in e.get("verus", []):
                a["verus_calls"] += 1
                a["verus_seconds"] += v["seconds"]

    L = ["# lcverus report", ""]
    L += ["## Outcome", "", "| status | count |", "|---|---|"]
    order = ["verified", "bug", "panic_free", "proof_failed", "spec_rejected", "unsupported", "shape", "fetch", "error", "spec_suspect", "paused"]
    for k in order:
        if statuses.get(k):
            L.append(f"| {k} | {statuses[k]} |")
    L += ["", "- **verified**: functional spec (`post`) + panic-freedom + termination proved for the unmodified rustgym code.",
          "- **panic_free**: functional proof failed, but no out-of-bounds / overflow / div-by-zero / non-termination proved under `pre`.",
          ""]
    if detail:
        L += ["### Why problems were skipped", "", "| reason | count |", "|---|---|"]
        L += [f"| `{k}` | {v} |" for k, v in detail.most_common(25)] + [""]

    L += ["## Problems", "",
          "| id | title | status | spec rounds | proof rounds | examples pre / post / neg rejected | critic | runtime | LLM tokens (in/out) | wall s |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        ev = r.get("events", [])
        tin = sum(c["input_tokens"] for e in ev for c in e.get("llm", []))
        tout = sum(c["output_tokens"] for e in ev for c in e.get("llm", []))
        secs = sum(e["seconds"] for e in ev)
        proof_rounds = Counter(e.get("mode") for e in ev if e["node"] == "verify")
        sm = spec_summary(r)
        rt = r.get("runtime") or {}
        rt_s = "–"
        if rt:
            exm = rt.get("examples", [])
            rt_s = f"ex {sum(x['match'] for x in exm)}/{len(exm)}, tests {rt.get('orig_tests')}"
        q = r.get("question") or {}
        title = f"{q.get('title', '')} ({q['difficulty']})" if q.get("difficulty") else q.get("title", "")
        crit = (r.get("critic") or {}).get("verdict", "–")
        pr = " + ".join(f"{v} {k}" for k, v in proof_rounds.items()) or "–"
        L.append(f"| [{r['pid']}](problems/p{r['pid']}.md) | {title} | {r['status']} | {r.get('spec_round', 0)} | {pr} | "
                 f"{_frac(sm['pre'])} / {_frac(sm['post'])} / {_frac(sm['neg'])} | {crit} | {rt_s} | {tin}/{tout} | {secs:.0f} |")

    L += ["", "## Where the time and tokens go (per LangGraph node)", "",
          "| node | runs | wall s | LLM calls (cached) | tokens in | tokens out | Verus calls | Verus s |", "|---|---|---|---|---|---|---|---|"]
    for name in ["fetch", "triage", "write_spec", "check_spec", "critic_spec", "human_review", "prove", "verify", "repair",
                 "safety_fallback", "runtime", "finalize"]:
        a = node_agg.get(name)
        if a:
            L.append(f"| {name} | {a['calls']} | {a['seconds']:.0f} | {a['llm_calls']} ({a['llm_cached']}) | {a['tokens_in']} | "
                     f"{a['tokens_out']} | {a['verus_calls']} | {a['verus_seconds']:.0f} |")

    resumed = [r for r in runs if r["_resumes"]]
    reviewed = [r for r in runs if r.get("review")]
    loops_spec = sum(max(r.get("spec_round", 0) - 1, 0) for r in runs)
    loops_proof = sum(sum(1 for e in r.get("events", []) if e["node"] == "repair") for r in runs)
    L += ["", "## Orchestration (LangGraph) at work", "",
          f"- **Checkpoints written**: {sum(cps.values())} across {len(cps)} threads (one thread per problem; any run can resume from its last node).",
          f"- **Resumed runs**: {len(resumed)} problems resumed from a checkpoint instead of restarting"
          + (f" ({', '.join(str(r['pid']) for r in resumed)})" if resumed else "") + ".",
          f"- **Cycles taken**: {loops_spec} spec revisions (write_spec ↺ check/critic), {loops_proof} proof repairs (verify ↺ repair), "
          f"{sum(1 for r in runs for e in r.get('events', []) if e['node'] == 'safety_fallback')} safety fallbacks.",
          f"- **Human-in-the-loop**: {len(reviewed)} specs went through `interrupt()` review"
          + (f" ({Counter(r['review']['action'] for r in reviewed)})" if reviewed else "") + ".",
          f"- **LLM cache hits**: {sum(a['llm_cached'] for a in node_agg.values())} of {sum(a['llm_calls'] for a in node_agg.values())} calls.",
          ""]
    lr = out_dir / "last_run.json"
    if lr.exists():
        j = json.loads(lr.read_text())
        L.append(f"- **Last batch**: {j['problems']} problems, max_concurrency={j['max_concurrency']}, wall {j['wall_s']:.0f}s "
                 f"vs {j['sum_node_s']:.0f}s summed node time (≈{j['sum_node_s'] / max(j['wall_s'], 1):.1f}× parallel speed-up).")
        L.append("")

    L += ["## Specs for human review", "",
          "Every proof is only as good as its spec. Review these (critic verdicts and example checks are automated hints, not proof).", ""]
    for r in runs:
        if r.get("spec_fns") and r["status"].split(":")[0] in ("verified", "panic_free", "proof_failed"):
            sm = spec_summary(r)
            issues = (r.get("critic") or {}).get("issues") or []
            L += [f"<details><summary><b>{r['pid']}. {(r.get('question') or {}).get('title', '')}</b> — {r['status']} — examples "
                  f"pre {_frac(sm['pre'])}, post {_frac(sm['post'])}, wrong outputs rejected {_frac(sm['neg'])}</summary>", "",
                  "```rust", r["spec_fns"], "```", ""]
            if issues:
                L += ["Critic notes:", *[f"- {i}" for i in issues], ""]
            L += ["</details>", ""]

    md = "\n".join(L)
    (out_dir / "summary.md").write_text(md)
    (out_dir / "summary.json").write_text(json.dumps(
        [{k: r.get(k) for k in ("pid", "status", "reason", "question", "spec_round", "proof_round", "mode", "critic", "runtime", "spec_hash")}
         for r in runs], indent=1))
    return md
