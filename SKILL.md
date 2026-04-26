---
name: drift-audit
version: "1.0.0"
description: Scan workspace tracker files for drift, staleness, contradictions, and orphaned artifacts. Cross-references PROJECTS.md, MEMORY.md, HEARTBEAT.md, TRIALS.md, cron jobs, skills, and vault projects against filesystem reality. Reports findings and logs a daily summary unless --no-log is used; never applies fixes.
allowed-tools: Bash, Read
user-invocable: true
metadata:
  openclaw:
    emoji: "🧭"
    requires:
      bins:
        - python3
        - bash
---

# drift-audit Skill

## Purpose

Run a comprehensive drift scan across the OpenClaw workspace. Detects stale tracker entries, broken references, contradictions between documentation and reality, root file ownership/cleanup candidates, cron/skill mismatches, and INFO-only wiki hygiene signals.

**Report-only for fixes.** This skill never applies corrections to tracker files. It prints findings and, by default, appends a short audit summary to today's daily memory log. Use `--no-log` for a fully read-only run.

## When to Run

- After major workspace changes (project migrations, cron reconfigurations)
- During weekly heartbeat vault maintenance
- When an agent acts on stale PROJECTS.md or MEMORY.md data and produces wrong results
- Proactively: `openclaw skills invoke drift-audit` or via cron

## Execution

When invoked, run the audit script:

```bash
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/audit.py
```

The script scans the workspace, prints a structured report to stdout, and appends a daily-log summary. Pass `--no-log` to skip the daily-log write.

To inspect OpenClaw dreaming auto-promotions in `MEMORY.md`, run the read-only helper:

```bash
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/review_promotions.py
```

## Report Format

The script outputs a structured report with severity levels:

- **🔴 CRITICAL:** Data integrity risk (false status, missing but referenced file, contradictions)
- **🟡 WARNING:** Stale data, outdated claims, drifting trackers
- **🟢 INFO:** Observations, cleanup opportunities, architectural notes

Each finding includes:
- File/location where the drift was detected
- What the file claims
- What reality shows
- Suggested fix

## Rules

- **Never apply fixes automatically.** All findings are reported; fixes require explicit approval.
- **Log by default.** Append a concise summary to today's daily memory unless `--no-log` is passed.
- **Cross-reference everything.** A claim in PROJECTS.md is only valid if the referenced file, cron, or skill exists.
- **Date-aware.** Entries with relative dates ("tomorrow", "next week") are checked against the actual calendar.
- **Silent on clean.** If no drift is found, output `🧭 Drift audit clean. No issues found.`
- **Be specific.** Include exact file paths, line numbers, and command outputs.

## How to act on findings

When a finding implicates content in a past `memory/YYYY-MM-DD.md` file, **do not edit that file**. Past daily logs are an event record — they capture what was true at that moment, including statements that later turned out wrong. Resolve drift by editing the current state file (`MEMORY.md`, `PROJECTS.md`, `HEARTBEAT.md`, `TRIALS.md`) and appending a correction to *today's* daily log. Curated state files are fair game; daily logs are append-only history.

OpenClaw dreaming auto-promotions are expected but temporary. Treat `## Promoted From Short-Term Memory (...)` sections as an inbox: fresh sections are INFO, stale unreviewed sections become WARNING, and resolution means curate durable items into normal `MEMORY.md` prose, dismiss noise, or mark deferred with `<!-- openclaw-promotion-reviewed:YYYY-MM-DD curated|dismissed|deferred -->`.

Root file cleanup is conservative. The script scans root `*.md` and observed backup siblings `*.md.*`; it does not treat `claws_vault/**/*.md` as root clutter. Unknown root files are INFO only. Use deterministic signals first (static classification, references, installed OpenClaw/runtime string matches). If still unclear, AI/web triage may help classify ownership, but must never automatically move/delete files.

## Deeper Audits

For OpenClaw-specific security drift (exposed ports, plugin supply chain, config hygiene), use the **healthcheck** skill.

## Daily Log Entry

After running, the script appends a summary to today's daily memory by default:

```
## Drift Audit — HH:MM
- [X] critical findings
- [Y] warnings
- [Z] info notes
- Top issue: [one-line summary]
```
