from pathlib import Path

_DIR = Path(__file__).parent


def render(name: str, **kw: str) -> str:
    text = (_DIR / f"{name}.md").read_text()
    kw.setdefault("VERUS_GUIDE", (_DIR / "verus_guide.md").read_text())
    kw.setdefault("FEWSHOT", (_DIR / "fewshot.md").read_text())
    kw.setdefault("MODE_NOTE", "")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", v)
    return text
