"""DeepSeek chat via langchain-deepseek, with a disk cache and usage accounting."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek

from .config import load

_db_lock = threading.Lock()


@dataclass
class Reply:
    text: str
    model: str
    role: str
    input_tokens: int
    output_tokens: int
    seconds: float
    cached: bool

    def usage(self) -> dict:
        d = asdict(self)
        d.pop("text")
        return d


@lru_cache(maxsize=None)
def _client(model: str, effort: str, max_tokens: int) -> ChatDeepSeek:
    cfg = load()["llm"]
    return ChatDeepSeek(
        model=model,
        api_key=load().api_key(),
        max_tokens=max_tokens,
        timeout=cfg["timeout_s"],
        max_retries=cfg["max_retries"],
        extra_body={"reasoning_effort": effort},
    )


def _text(msg) -> str:
    if isinstance(msg.content, str):
        return msg.content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in msg.content)


def _db() -> sqlite3.Connection:
    path = load().path("cache") / "llm.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("create table if not exists replies (key text primary key, value text)")
    return con


def chat(role: str, system: str, user: str, *, sample: int = 0, use_cache: bool = True,
         required_tags: tuple[str, ...] = ()) -> Reply:
    """One chat completion for a pipeline role (spec_writer, critic, prover, ...).

    A reply that is empty or lacks a closing `</tag>` for any of `required_tags` was truncated by the
    output budget (reasoning tokens count against it): retry once with twice the budget, and never cache it.
    """
    # "body|suspected_bug" = either closing tag will do
    complete = lambda t: bool(t.strip()) and all(any(f"</{a}>" in t for a in tag.split("|")) for tag in required_tags)
    rc = load()["llm"]["roles"][role]
    model, effort, max_tokens = rc["model"], rc["effort"], rc["max_tokens"]
    key = hashlib.sha256(json.dumps([model, effort, system, user, sample]).encode()).hexdigest()
    if use_cache:
        with _db_lock:
            con = _db()
            row = con.execute("select value from replies where key = ?", (key,)).fetchone()
            con.close()
        if row and complete(json.loads(row[0])["text"]):
            v = json.loads(row[0])
            return Reply(v["text"], model, role, v["input_tokens"], v["output_tokens"], 0.0, True)
    t0 = time.time()
    tin = tout = 0
    for budget in (max_tokens, min(2 * max_tokens, 384000)):
        msg = _client(model, effort, budget).invoke([SystemMessage(system), HumanMessage(user)])
        u = msg.usage_metadata or {}
        tin, tout = tin + u.get("input_tokens", 0), tout + u.get("output_tokens", 0)
        text = _text(msg)
        if complete(text):
            break
    reply = Reply(text, model, role, tin, tout, time.time() - t0, False)
    if not complete(text):
        return reply  # never cache a truncated reply
    with _db_lock:
        con = _db()
        con.execute(
            "insert or replace into replies values (?, ?)",
            (key, json.dumps({"text": text, "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens})),
        )
        con.commit()
        con.close()
    return reply


def section(text: str, tag: str) -> str | None:
    """Content of <tag>...</tag>, with any ``` fences stripped."""
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    if not m:
        return None
    lines = m.group(1).strip().splitlines()
    fence = lambda ln: re.fullmatch(r"\s*```[a-zA-Z]*\s*", ln) is not None
    while lines and fence(lines[0]):
        lines.pop(0)
    while lines and fence(lines[-1]):
        lines.pop()
    return "\n".join(lines).strip()


def json_section(text: str, tag: str) -> dict | None:
    s = section(text, tag)
    if s is None:
        return None
    try:
        return json.loads(s)
    except ValueError:
        m = re.search(r"\{.*\}", s, re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except ValueError:
            return None
