#!/usr/bin/env python3
"""
Review OpenClaw dreaming auto-promotions in MEMORY.md.

Read-only helper. It lists unreviewed `Promoted From Short-Term Memory` sections,
the promoted candidates, source snippets, age, and suggested action.
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
MEMORY_PATH = WORKSPACE / "MEMORY.md"

SECTION_RE = re.compile(
    r"## Promoted From Short-Term Memory \((\d{4}-\d{2}-\d{2})\)\n(?P<body>.*?)(?=\n## |\Z)",
    flags=re.DOTALL,
)
MARKER_RE = re.compile(r"<!--\s*openclaw-memory-promotion:([^\n]+?)\s*-->")
BULLET_RE = re.compile(r"^- (?P<text>.*?)(?: \[score=.*? source=(?P<source>[^\]]+)\])?$", flags=re.MULTILINE)
REVIEW_RE = re.compile(
    r"<!--\s*openclaw-promotion-reviewed:(\d{4}-\d{2}-\d{2})\s+(curated|dismissed|deferred)\s*-->",
    flags=re.IGNORECASE,
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def normalize_source(raw: str | None) -> tuple[str | None, int | None, int | None]:
    if not raw:
        return None, None, None
    match = re.match(r"(.+):(\d+)-(\d+)$", raw.strip())
    if not match:
        return raw.strip(), None, None
    return match.group(1), int(match.group(2)), int(match.group(3))


def source_excerpt(source: str | None, start: int | None, end: int | None) -> str:
    if not source or start is None or end is None:
        return ""
    path = WORKSPACE / source
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return "[source missing]"
    excerpt = " ".join(lines[max(0, start - 1):end]).strip()
    return excerpt


def suggest_action(text: str, source: str | None) -> str:
    lower = text.lower()
    if "score=" in lower or "recalls=" in lower:
        return "review"
    if any(token in lower for token in ["morning report", "evening report", "items scanned", "daily p&l"]):
        return "dismiss — routine operational report"
    if any(token in lower for token in ["trial window", "backup:", "deployed", "fixes", "smoke test"]):
        return "curate if not already represented in project memory"
    if "compiled wiki" in lower or "wiki vault" in lower:
        return "verify path, then curate or dismiss"
    if source and source.startswith("memory/"):
        return "review source; decide curate/dismiss/defer"
    return "review"


def main() -> int:
    parser = argparse.ArgumentParser(description="List unreviewed OpenClaw MEMORY.md auto-promotions.")
    parser.add_argument("--all", action="store_true", help="Include sections already marked reviewed.")
    parser.add_argument("--memory", default=str(MEMORY_PATH), help="Path to MEMORY.md")
    args = parser.parse_args()

    memory_path = Path(args.memory).expanduser()
    text = read_text(memory_path)
    if not text:
        print(f"No MEMORY.md found at {memory_path}")
        return 1

    reviewed = {m.group(1): m.group(2).lower() for m in REVIEW_RE.finditer(text)}
    today = datetime.now().date()
    sections = list(SECTION_RE.finditer(text))
    if not sections:
        print("No auto-promotion sections found.")
        return 0

    shown = 0
    for section in sections:
        date_str = section.group(1)
        status = reviewed.get(date_str)
        if status and not args.all:
            continue
        try:
            age_days = (today - datetime.strptime(date_str, "%Y-%m-%d").date()).days
        except ValueError:
            age_days = None
        body = section.group("body")
        bullets = list(BULLET_RE.finditer(body))
        markers = list(MARKER_RE.finditer(body))
        shown += 1
        age = f"{age_days}d" if age_days is not None else "unknown"
        print(f"## {date_str} — {len(markers)} candidate(s), age={age}, reviewed={status or 'no'}")
        print(f"Suggested marker after review: <!-- openclaw-promotion-reviewed:{date_str} curated|dismissed|deferred -->")
        for index, bullet in enumerate(bullets, 1):
            candidate = bullet.group("text").strip()
            source, start, end = normalize_source(bullet.group("source"))
            excerpt = source_excerpt(source, start, end)
            print(f"\n{index}. {candidate}")
            if source:
                span = f":{start}-{end}" if start is not None and end is not None else ""
                print(f"   source: {source}{span}")
            if excerpt and excerpt != candidate:
                print(f"   excerpt: {excerpt}")
            print(f"   suggested: {suggest_action(candidate, source)}")
        print("")

    if shown == 0:
        print("No unreviewed auto-promotion sections found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
