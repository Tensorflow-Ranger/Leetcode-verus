"""Configuration: config.yaml + .env, with paths resolved against the project root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    raw: dict

    def __getitem__(self, key):
        return self.raw[key]

    def path(self, key: str) -> Path:
        p = Path(self.raw["paths"][key])
        return p if p.is_absolute() else ROOT / p

    @property
    def verus_bin(self) -> Path:
        return ROOT / self.raw["verus"]["bin"]

    @property
    def z3_bin(self) -> Path:
        return ROOT / self.raw["verus"]["z3"]

    def api_key(self) -> str:
        name = self.raw["llm"]["api_key_env"]
        key = os.environ.get(name) or dotenv_values(ROOT / ".env").get(name)
        if not key:
            raise RuntimeError(f"DeepSeek API key not found: set {name} in .env or the environment")
        return key


@lru_cache(maxsize=1)
def load(path: str | None = None) -> Config:
    with open(path or ROOT / "config.yaml") as f:
        return Config(yaml.safe_load(f))
