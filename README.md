# drift-audit

A report-only drift scanner for OpenClaw agent workspaces. Detects stale tracker entries, broken references, contradictions between documentation and reality, orphaned files, cron/skill mismatches, wiki hygiene drift, root-file ownership drift, and concrete claims that need independent validation.

**Never applies fixes.** Findings are reported for human review and explicit approval. By default, the script also appends a concise audit summary to today's daily memory log; pass `--no-log` for a fully read-only run.

## What it scans

| Area | Checks |
|------|--------|
| **PROJECTS.md** | Stale dates, relative-time rot, missing file references, contradictions with MEMORY.md, ghost projects |
| **MEMORY.md** | Line count, stale model/plugin claims, contradictions, uncurated auto-promotion sections |
| **HEARTBEAT.md** | Broken file references, trial expiry, vault path drift |
| **TRIALS.md** | Evaluation dates passed or approaching |
| **AI claim validation** | The invoking agent reviews important current-state claims and chooses suitable read-only validation tools for each case |
| **Cron jobs** | Skill/cron mismatches and project claims that imply a missing scheduled job |
| **Skills** | Skills with no cron registration (on-demand vs orphaned) |
| **Workspace root** | Backup files, reviewed archive/move candidates, dynamic OpenClaw-managed file signals, unclassified root markdown-like files |
| **Daily logs** | Today's file existence |
| **Dreaming** | Cron delivery configuration vs DREAMS.md canonical status |
| **Wiki hygiene** | INFO-only guardrails for missing/tiny wiki sources, generated lint/contradiction reports, and source-sync/state anomalies |

## Install

```bash
# Clone into your OpenClaw workspace skills directory
git clone https://github.com/rimpe/drift-audit.git ~/.openclaw/workspace/skills/drift-audit

# Or copy manually
cp -r drift-audit ~/.openclaw/workspace/skills/
```

## Usage

```bash
# Run the audit and append a daily-log summary
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/audit.py

# Fully read-only run: print report only, no daily-log summary
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/audit.py --no-log

# Review OpenClaw dreaming auto-promotions in MEMORY.md
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/review_promotions.py

# Or invoke via OpenClaw skill system
openclaw skills invoke drift-audit
```

## Output

Structured report with severity levels:

- **🔴 CRITICAL:** Data integrity risk — contradictions, false completed state, missing referenced files, missing scheduled jobs, unreadable required state
- **🟡 WARNING:** Stale data, approaching deadlines, drifting trackers, unverified concrete claims
- **🟢 INFO:** Observations, cleanup opportunities, architectural notes

Example:

```
🧭 Drift Audit Report
Generated: 2026-04-24 19:32

Summary: 8 critical, 23 warnings, 17 info

🔴 [CRITICAL] MEMORY.md
   Line: 102
   Claim: Claims firewall is DISABLED
   Reality: PROJECTS.md says firewall was enabled
   Fix: Reconcile the two files
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | No critical findings |
| 1 | At least one critical finding |

## How to act on findings

drift-audit reports state, it doesn't fix it. When acting on a finding, follow this rule:

**Never rewrite past daily logs.** Past `memory/YYYY-MM-DD.md` files are an event record — they capture what was true at that moment, including statements that later turned out wrong. Resolving drift by editing the current state file (`MEMORY.md`, `PROJECTS.md`, `HEARTBEAT.md`, `TRIALS.md`) and appending a correction to *today's* daily log preserves the historical signal. Overwriting a past log destroys it.

Curated state files are fair game to edit or delete stale sections. Daily logs are append-only history.

### Auto-promotion review

OpenClaw dreaming appends strong short-term candidates to `MEMORY.md` under `## Promoted From Short-Term Memory (...)`. Treat these sections as a temporary long-term-memory inbox:

- Fresh sections (≤48h) are INFO.
- Unreviewed stale sections (>48h) are WARNING.
- Use `scripts/review_promotions.py` to inspect candidates and source lines.
- Resolve each section by curating durable items into normal `MEMORY.md` prose, dismissing noise, or deferring with a reason.
- Optional review marker after resolution:
  `<!-- openclaw-promotion-reviewed:YYYY-MM-DD curated|dismissed|deferred -->`

## AI Claim Validation

The Python script is intentionally deterministic and domain-neutral. It should not hardcode every possible way to verify claims. When invoked through an agent, the agent should perform a second pass:

1. Identify concrete current-state claims that matter.
2. Infer the right read-only evidence source from the claim and local context.
3. Use only non-mutating commands, tools, skills, APIs, docs, or file reads.
4. Report verified, contradicted, and unverified claims with evidence.

Example: if a tracker claims a host firewall is enabled, the agent should determine the host OS and choose the relevant read-only firewall-status command. The script should not need to know that command in advance.

## Running as a cron job

Add to `cron/jobs.json` for weekly automated scanning:

```json
{
  "name": "Weekly Drift Audit",
  "schedule": { "expr": "0 15 * * 0", "tz": "Europe/Helsinki" },
  "payload": {
    "message": "Invoke the drift-audit skill"
  },
  "delivery": {
    "mode": "announce",
    "channel": "telegram",
    "to": "YOUR_TOPIC"
  }
}
```

## Customization

Edit `scripts/audit.py` to adjust:

- Root file classification sets in `scripts/audit.py` (`CORE_MARKDOWN_FILES`, `OPENCLAW_MANAGED_ROOT_FILES`, archive/move candidates)
- Date thresholds for staleness
- Severity mappings

### Root file ownership policy

Root cleanup is conservative. The audit scans root `*.md` and observed backup siblings `*.md.*`, but it does **not** scan `claws_vault/**/*.md` as root clutter. For unknown root files, deterministic checks come first: static classification, rollback/trial references, and installed OpenClaw/runtime string references. If ownership is still unclear, use AI/web triage to classify the file as likely OpenClaw-managed, user note, backup, project doc, or archive candidate. AI/web output is advisory only: never auto-delete or auto-move based on it.

### Domain-specific validation policy

The script intentionally keeps domain-specific claim validation out of code. Add broad deterministic checks only when they are stable across workspaces; otherwise document the validation workflow in `SKILL.md` so the invoking agent can choose the right read-only evidence source.

## Requirements

- Python 3.8+
- Read access to `~/.openclaw/workspace/` and `~/.openclaw/cron/jobs.json`

## License

MIT

## Contributing

Issues and PRs welcome. This was built for the [OpenClaw](https://openclaw.ai) agent system but adapts to any workspace with:

- `PROJECTS.md` (project tracker)
- `MEMORY.md` (long-term memory)
- `HEARTBEAT.md` / `TRIALS.md` (process docs)
- `memory/` (daily logs)
- `skills/` (skill directory)
