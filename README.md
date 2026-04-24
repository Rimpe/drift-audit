# drift-audit

A report-only drift scanner for OpenClaw agent workspaces. Detects stale tracker entries, broken references, contradictions between documentation and reality, orphaned files, and cron/skill mismatches.

**Never modifies files.** Findings are reported for human review and explicit approval.

## What it scans

| Area | Checks |
|------|--------|
| **PROJECTS.md** | Stale dates, relative-time rot, missing file references, contradictions with MEMORY.md, ghost projects |
| **MEMORY.md** | Line count, stale model/plugin claims, contradictions, garbled auto-promotion blocks |
| **HEARTBEAT.md** | Broken file references, trial expiry, vault path drift |
| **TRIALS.md** | Evaluation dates passed or approaching |
| **Cron jobs** | Invalid expressions (6-field), idle jobs, skill/cron mismatches |
| **Skills** | Skills with no cron registration (on-demand vs orphaned) |
| **Workspace root** | Orphaned backup files, non-core markdown drift |
| **Daily logs** | Today's file existence |
| **Dreaming** | Cron delivery configuration vs DREAMS.md canonical status |

## Install

```bash
# Clone into your OpenClaw workspace skills directory
git clone https://github.com/rimpe/drift-audit.git ~/.openclaw/workspace/skills/drift-audit

# Or copy manually
cp -r drift-audit ~/.openclaw/workspace/skills/
```

## Usage

```bash
# Run the audit
python3 ~/.openclaw/workspace/skills/drift-audit/scripts/audit.py

# Or invoke via OpenClaw skill system
openclaw skills invoke drift-audit
```

## Output

Structured report with severity levels:

- **🔴 CRITICAL:** Data integrity risk — contradictions, missing referenced files, invalid cron expressions
- **🟡 WARNING:** Stale data, approaching deadlines, drifting trackers
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

- `CORE_FILES` — files considered essential (not orphaned)
- Date thresholds for staleness
- Severity mappings

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
