"""LeetCode problem metadata via the public GraphQL endpoint (cached on disk)."""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

import httpx
from markdownify import markdownify

from ..config import load

URL = "https://leetcode.com/graphql"
HEADERS = {"Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0 (lcverus research)"}

Q_SEARCH = """query q($f: QuestionListFilterInput) {
  questionList(categorySlug: "", limit: 10, skip: 0, filters: $f) { data { questionFrontendId titleSlug } } }"""
Q_QUESTION = """query q($s: String!) { question(titleSlug: $s) {
  questionFrontendId title titleSlug difficulty isPaidOnly content exampleTestcaseList metaData } }"""


def _post(query: str, variables: dict) -> dict:
    for attempt in range(4):
        try:
            r = httpx.post(URL, json={"query": query, "variables": variables}, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()["data"]
        except (httpx.HTTPError, KeyError, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError


def _cache_dir() -> Path:
    d = load().path("cache") / "leetcode"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch(pid: int) -> dict | None:
    """Question dict for frontend id `pid`, or None if it can't be resolved."""
    cache = _cache_dir() / f"{pid}.json"
    if cache.exists():
        return json.loads(cache.read_text()) or None
    rows = _post(Q_SEARCH, {"f": {"searchKeywords": str(pid)}})["questionList"]["data"]
    slug = next((r["titleSlug"] for r in rows if r["questionFrontendId"] == str(pid)), None)
    q = _post(Q_QUESTION, {"s": slug})["question"] if slug else None
    cache.write_text(json.dumps(q or {}, indent=1))
    time.sleep(0.3)
    return q


def to_markdown(q: dict) -> str:
    # markdownify drops <sup>, turning 10<sup>5</sup> into "105": keep exponents explicit.
    content = re.sub(r"<sup>(.*?)</sup>", r"^\1", q["content"])
    content = re.sub(r"<sub>(.*?)</sub>", r"_\1", content)
    body = markdownify(content, heading_style="ATX", bullets="-").strip()
    body = re.sub(r"\n{3,}", "\n\n", body).replace("\xa0", " ")
    return f"# {q['questionFrontendId']}. {q['title']}\n\nDifficulty: {q['difficulty']}\n\n{body}\n"


def _text(content_html: str) -> str:
    t = re.sub(r"<sup>(.*?)</sup>", r"^\1", content_html)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).replace("\xa0", " ")


def parse_examples(q: dict) -> list[dict]:
    """[{inputs: [json values per param], output: json value | None, raw_output: str}]"""
    meta = json.loads(q["metaData"])
    nparams = len(meta.get("params", []))
    outs = re.findall(r"Output:\s*(.+)", _text(q["content"]))
    examples = []
    for k, case in enumerate(q.get("exampleTestcaseList") or []):
        lines = [ln for ln in case.split("\n") if ln.strip()]
        try:
            inputs = [json.loads(ln) for ln in lines]
        except ValueError:
            inputs = None
        if inputs is not None and len(inputs) != nparams:
            inputs = None
        raw = outs[k].strip() if k < len(outs) else ""
        try:
            out = json.loads(raw)
        except ValueError:
            out = None
        examples.append({"inputs": inputs, "output": out, "raw_output": raw})
    return examples
