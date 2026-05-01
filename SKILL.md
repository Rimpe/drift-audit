---
name: drift-audit
version: "1.0.0"
description: Scan workspace tracker files for drift, staleness, contradictions, orphaned artifacts, and concrete claims that need validation. Cross-references PROJECTS.md, MEMORY.md, HEARTBEAT.md, TRIALS.md, cron jobs, skills, and vault projects. The agent must choose read-only validation tools appropriate to each claim. Report-only, never modifies files.
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

Run a comprehensive drift scan across the OpenClaw workspace. Detects stale tracker entries, broken references, contradictions between documentation and reality, root file ownership/cleanup candidates, cron/skill mismatches, INFO-only wiki hygiene signals, and concrete claims that need independent validation.

**Report-only for fixes.** This skill never applies corrections to tracker files. It prints findings and, by default, appends a short audit summary to today's daily memory log. Use `--no-log` for a fully read-only run.

## When to Run

- After major workspace changes (project migrations, cron reconfigurations)
- During weekly heartbeat vault maintenance
- When an agent acts on stale PROJECTS.md or MEMORY.md data and produces wrong results
- Proactively: `openclaw skills invoke drift-audit` or via cron

## Execution

When invoked, do two phases.

### Phase 1 — Deterministic Scan

Run the audit script:

```bash
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/audit.py
```

The script scans the workspace, prints a structured report to stdout, and appends a daily-log summary. Pass `--no-log` to skip the daily-log write.

```bash
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/audit.py --no-log
```

To inspect OpenClaw dreaming auto-promotions in `MEMORY.md`, run the read-only helper:

```bash
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/review_promotions.py
```

### Phase 2 — AI Claim Validation

After the script output, inspect current-state files and the findings for concrete claims that matter. The agent, not the script, decides what read-only evidence is appropriate.

Current-state files include `PROJECTS.md`, `MEMORY.md`, `HEARTBEAT.md`, `TRIALS.md`, and relevant project files under `claws_vault/03_creating/**/{README,status,checklist,notes}.md`. Past `memory/YYYY-MM-DD.md` files are historical evidence, not current truth.

For each important claim:
1. Extract the exact claim and source line.
2. Classify what would prove or disprove it: filesystem, config, service/runtime, cron, package manager, external API, git history, docs, database, or another domain-specific source.
3. Choose read-only commands, tools, or skills that fit that claim. Do not rely on a fixed command list.
4. Run only non-mutating validation. If a command may write, install, reload, repair, or change state, do not run it.
5. If validation is unavailable, timed out, or ambiguous, report the claim as unverified.
6. Report the evidence, command/tool used, result, and suggested non-mutating next step.

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

- **Never modify files.** All findings are reported; fixes require explicit approval.
- **Validate concrete claims.** If a current-state file claims something measurable, prefer direct read-only evidence over another document agreeing with it.
- **No hardcoded validation worldview.** The agent must infer the right validation approach from the claim and local context.
- **Cross-reference everything.** A claim in PROJECTS.md is only valid if the referenced file, cron, skill, project artifact, runtime state, or other appropriate evidence confirms it.
- **Unknown is a finding.** If a claim cannot be validated safely, report it as unverified instead of silently passing.
- **Date-aware.** Entries with relative dates ("tomorrow", "next week") are checked against the actual calendar.
- **Silent on clean.** If no drift is found, output `🧭 Drift audit clean. No issues found.`
- **Be specific.** Include exact file paths, line numbers, and command outputs.

## Validation Examples

These are examples of reasoning, not a fixed checklist:

- A firewall claim may require discovering the host OS and then choosing the platform's read-only firewall status command.
- A cron claim may require reading cron config and checking runtime history with OpenClaw cron inspection commands.
- A package-update claim may require the package manager's read-only outdated/list command.
- A project completion claim may require checking for the claimed artifact, tests, cron entry, commit, or status output.
- An external-service claim may require official docs, API status, or a read-only CLI/API query if credentials and permissions already exist.

Validation must never enable services, install updates, edit configs, reload launch agents, delete files, write databases, or mutate remote systems.

## How to act on findings

When a finding implicates content in a past `memory/YYYY-MM-DD.md` file, **do not edit that file**. Past daily logs are an event record — they capture what was true at that moment, including statements that later turned out wrong. Resolve drift by editing the current state file (`MEMORY.md`, `PROJECTS.md`, `HEARTBEAT.md`, `TRIALS.md`) and appending a correction to *today's* daily log. Curated state files are fair game; daily logs are append-only history.

OpenClaw dreaming auto-promotions are expected but temporary. Treat `## Promoted From Short-Term Memory (...)` sections as an inbox: fresh sections are INFO, stale unreviewed sections become WARNING, and resolution means curate durable items into normal `MEMORY.md` prose, dismiss noise, or mark deferred with `<!-- openclaw-promotion-reviewed:YYYY-MM-DD curated|dismissed|deferred -->`.

Root file cleanup is conservative. The script scans root `*.md` and observed backup siblings `*.md.*`; it does not treat `claws_vault/**/*.md` as root clutter. Unknown root files are INFO only. Use deterministic signals first (static classification, references, installed OpenClaw/runtime string matches). If still unclear, AI/web triage may help classify ownership, but must never automatically move/delete files.

## Deeper Audits

drift-audit validates claims it already sees in current-state files. For broad discovery that is not tied to an existing claim, use the relevant domain skill, audit tool, or read-only inspection command and clearly label it as broader discovery.

## Daily Log Entry

After running, the script appends a summary to today's daily memory by default:

```
## Drift Audit — HH:MM
- [X] critical findings
- [Y] warnings
- [Z] info notes
- Top issue: [one-line summary]
```
