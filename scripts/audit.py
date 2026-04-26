#!/usr/bin/env python3
"""
drift-audit: Scan workspace tracker files for drift, staleness, contradictions,
and orphaned artifacts. Never applies fixes; writes a daily-log summary unless
--no-log is passed.

Usage:
    python3 audit.py [--no-log]

Output:
    Structured drift report with severity levels to stdout.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────
WORKSPACE = Path.home() / ".openclaw" / "workspace"
CRON_FILE = Path.home() / ".openclaw" / "cron" / "jobs.json"
VAULT = WORKSPACE / "claws_vault"
MEMORY_DIR = WORKSPACE / "memory"
SKILLS_DIR = WORKSPACE / "skills"

# Files that are considered "core" and should not be flagged as orphaned
CORE_FILES = {
    "AGENTS.md", "AGENTS.md.bak", "BACKUP_PLAN.md", "DREAMS.md",
    "EXEC_APPROVALS_PLAN.md", "HEALTH-CHECK.md", "HEARTBEAT.md",
    "HEARTBEAT.md.bak", "HEARTBEAT_PAYLOAD_TEMPLATE.txt",
    "IDENTITY.md", "INITIAL_HEARTBEAT_STATE.json", "MEMORY.md",
    "MEMORY.md.backup-2026-04-06-1135", "MEMORY.md.old260420.md",
    "MONITOR_MULTI_REPO_PLAN.md", "OBSIDIAN_INTEGRATION_PLAN.md",
    "PDF_INSTALL_PLAN.md", "PROJECTS.md", "QMD_INSTALL_ANALYSIS_2026-04-06.md",
    "SOUL.md", "TOOLS.md", "TRIALS.md", "USER.md",
    "openclaw.json", "openclaw.json.backup-20260422-1025",
}

FINDINGS = []
ARGS = None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan OpenClaw workspace trackers for drift. Writes a daily-log summary by default."
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not append the audit summary to today's daily memory log.",
    )
    return parser.parse_args()


def find(sev: str, source: str, line: int, claim: str, reality: str, fix: str):
    FINDINGS.append({
        "severity": sev,
        "source": source,
        "line": line,
        "claim": claim,
        "reality": reality,
        "fix": fix,
    })


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def line_no(text: str, substring: str) -> int:
    for i, line in enumerate(text.splitlines(), 1):
        if substring in line:
            return i
    return 0


# ── 1. PROJECTS.md drift ────────────────────────────────────────────────
def check_projects_md():
    text = read_text(WORKSPACE / "PROJECTS.md")
    if not text:
        find("CRITICAL", "PROJECTS.md", 0, "File missing", "File not found",
             "Recreate PROJECTS.md or investigate why it was deleted")
        return

    # Stale dates
    for match in re.finditer(
        r'(?i)(2026-0[1-3]-\d{2}|2026-04-0[1-5])\b', text
    ):
        date_str = match.group(1)
        line = text[:match.start()].count("\n") + 1
        find(
            "WARNING", "PROJECTS.md", line,
            f"Reference to past date: {date_str}",
            f"Today is {datetime.now().strftime('%Y-%m-%d')}",
            "Update or remove the stale date reference",
        )

    # Relative-time drift: "tomorrow", "next week", "start tomorrow"
    for match in re.finditer(
        r'(?i)\b(tomorrow|next week|start .* tomorrow|process to start tomorrow)\b',
        text,
    ):
        line = text[:match.start()].count("\n") + 1
        find(
            "WARNING", "PROJECTS.md", line,
            f"Relative-time claim: '{match.group(1)}'",
            "Relative dates rot immediately; no way to verify if they were met",
            "Replace with absolute dates or remove once the event has passed",
        )

    # References to files that don't exist
    for match in re.finditer(r'`(memory/[^`]+)`', text):
        ref = match.group(1)
        # Skip template patterns (documentation examples)
        if "YYYY-MM-DD" in ref or re.search(r'\b[A-Z]{2,}-\b', ref):
            continue
        path = WORKSPACE / ref
        if not path.exists():
            line = text[:match.start()].count("\n") + 1
            find(
                "CRITICAL", "PROJECTS.md", line,
                f"References file that does not exist: `{ref}`",
                "File missing on disk",
                f"Create the file or remove the reference",
            )

    # Check for contradictions with MEMORY.md
    mem_text = read_text(WORKSPACE / "MEMORY.md")
    if "Firewall DISABLED" in mem_text and "firewall enabled" in text.lower():
        find(
            "CRITICAL", "PROJECTS.md", line_no(text, "firewall enabled"),
            "Claims firewall is enabled (resolved)",
            "MEMORY.md says 'Firewall DISABLED (critical)'",
            "Reconcile the two files; only one can be true",
        )

    # Cleanup notes referencing already-removed items
    if "original heartbeat" in text.lower() and "can be deleted" in text.lower():
        find(
            "WARNING", "PROJECTS.md", line_no(text, "original heartbeat"),
            "Cleanup note: original heartbeat job can be deleted after 2026-05-07",
            "Daily log 2026-04-23 confirms original heartbeat was already removed",
            "Remove the stale cleanup note",
        )

    # Check vault project links
    for match in re.finditer(r'`claws_vault/([^`]+)`', text):
        ref = match.group(1)
        path = WORKSPACE / "claws_vault" / ref
        if not path.exists():
            line = text[:match.start()].count("\n") + 1
            find(
                "CRITICAL", "PROJECTS.md", line,
                f"References vault path that does not exist: `claws_vault/{ref}`",
                "Path missing on disk",
                "Create the vault project or remove the reference",
            )


# ── 2. MEMORY.md drift ──────────────────────────────────────────────────
def check_memory_md():
    text = read_text(WORKSPACE / "MEMORY.md")
    if not text:
        return

    # Line count
    line_count = len(text.splitlines())
    if line_count > 150:
        find(
            "WARNING", "MEMORY.md", 0,
            f"Line count: {line_count} (limit: 150)",
            "Exceeds the 150-line budget",
            "Archive old entries to memory/archive/",
        )

    # Stale model/plugin/version claims
    for match in re.finditer(
        r'(?i)primary model[:\s]+([a-z0-9\-/\.]+)', text
    ):
        model = match.group(1)
        line = text[:match.start()].count("\n") + 1
        # We can't know the current model without querying, so flag for review
        find(
            "INFO", "MEMORY.md", line,
            f"Hard-coded model claim: '{model}'",
            "Model assignments can change silently via config",
            "Verify this is still the primary model in openclaw.json",
        )

    # Contradiction with PROJECTS.md
    proj_text = read_text(WORKSPACE / "PROJECTS.md")
    if "Firewall DISABLED" in text and "firewall enabled" in proj_text.lower():
        find(
            "CRITICAL", "MEMORY.md", line_no(text, "Firewall DISABLED"),
            "Claims firewall is DISABLED",
            "PROJECTS.md says firewall was enabled (resolved)",
            "Reconcile the two files; only one can be true",
        )

    # Stale phase claims
    if "Phase 4 (weekly reporting) pending" in text:
        # Check if weekly report cron exists
        cron_data = load_cron_jobs()
        if cron_data:
            for job in cron_data.get("jobs", []):
                if "weekly" in job.get("name", "").lower() and "report" in job.get("name", "").lower():
                    if job.get("enabled"):
                        find(
                            "WARNING", "MEMORY.md", line_no(text, "Phase 4"),
                            "Claims Phase 4 (weekly reporting) is pending",
                            f"Cron job '{job['name']}' is enabled and scheduled",
                            "Update status to reflect implementation",
                        )
                        break

    # Garbled auto-promoted blocks
    if "openclaw-memory-promotion" in text:
        line = line_no(text, "openclaw-memory-promotion")
        find(
            "WARNING", "MEMORY.md", line,
            "Contains raw auto-promotion block (openclaw-memory-promotion)",
            "Auto-promoted content was never curated into proper prose",
            "Remove or rewrite the garbled block",
        )

    # Check for stale daily log references
    for match in re.finditer(r'memory/2026-0[1-3]-\d{2}\.md', text):
        ref = match.group(0)
        line = text[:match.start()].count("\n") + 1
        find(
            "INFO", "MEMORY.md", line,
            f"References old daily log: {ref}",
            "Daily logs older than 30 days are typically archived",
            "Verify the reference is still relevant; consider archiving",
        )


# ── 3. HEARTBEAT.md drift ──────────────────────────────────────────────
def check_heartbeat_md():
    text = read_text(WORKSPACE / "HEARTBEAT.md")
    if not text:
        return

    # Broken file references
    for match in re.finditer(r'`memory/([^`]+)`', text):
        ref = match.group(1)
        # Skip template patterns (documentation examples)
        if "YYYY-MM-DD" in ref or re.search(r'\b[A-Z]{2,}-\b', ref):
            continue
        path = WORKSPACE / "memory" / ref
        if not path.exists():
            # Check if .json variant exists
            json_path = path.with_suffix(".json")
            if json_path.exists():
                line = text[:match.start()].count("\n") + 1
                find(
                    "WARNING", "HEARTBEAT.md", line,
                    f"References `{ref}` but only `{ref.replace('.md', '.json')}` exists",
                    "Wrong file extension in documentation",
                    f"Update reference to `{ref.replace('.md', '.json')}`",
                )
            else:
                line = text[:match.start()].count("\n") + 1
                find(
                    "CRITICAL", "HEARTBEAT.md", line,
                    f"References file that does not exist: `memory/{ref}`",
                    "File missing on disk",
                    "Create the file or fix the reference",
                )

    # Trial dates
    for match in re.finditer(
        r'(?i)until\s+(2026-\d{2}-\d{2})', text
    ):
        end_date = datetime.strptime(match.group(1), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        days_left = (end_date - datetime.now(timezone.utc)).days
        line = text[:match.start()].count("\n") + 1
        if days_left < 0:
            find(
                "CRITICAL", "HEARTBEAT.md", line,
                f"Trial ended {abs(days_left)} days ago ({match.group(1)})",
                "Evaluation date has passed but no decision logged",
                "Evaluate the trial per TRIALS.md and update or remove the section",
            )
        elif days_left <= 7:
            find(
                "WARNING", "HEARTBEAT.md", line,
                f"Trial ends in {days_left} days ({match.group(1)})",
                "Evaluation date approaching",
                "Prepare evaluation per TRIALS.md criteria",
            )

    # Check for references to files in claws_vault
    for match in re.finditer(r'`claws_vault/([^`]+)`', text):
        ref = match.group(1)
        path = WORKSPACE / "claws_vault" / ref
        if not path.exists():
            line = text[:match.start()].count("\n") + 1
            find(
                "WARNING", "HEARTBEAT.md", line,
                f"References vault file that does not exist: `claws_vault/{ref}`",
                "File missing on disk",
                "Create the file or fix the reference",
            )


# ── 4. TRIALS.md drift ─────────────────────────────────────────────────
def check_trials_md():
    text = read_text(WORKSPACE / "TRIALS.md")
    if not text:
        return

    for match in re.finditer(
        r'(?i)(\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})', text
    ):
        start, end = match.group(1), match.group(2)
        end_date = datetime.strptime(end, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        days_left = (end_date - datetime.now(timezone.utc)).days
        line = text[:match.start()].count("\n") + 1
        if days_left < 0:
            find(
                "CRITICAL", "TRIALS.md", line,
                f"Trial period ended {abs(days_left)} days ago ({end})",
                "Evaluation date has passed but trial section still exists",
                "Evaluate per TRIALS.md graduation/removal criteria and clean up",
            )
        elif days_left <= 7:
            find(
                "WARNING", "TRIALS.md", line,
                f"Trial evaluation due in {days_left} days ({end})",
                "Evaluation approaching",
                "Prepare evaluation report per TRIALS.md",
            )


# ── 5. Orphaned backup files ───────────────────────────────────────────
def check_orphaned_files():
    bak_files = list(WORKSPACE.glob("*.bak")) + list(WORKSPACE.glob("*.bak.*"))
    for f in bak_files:
        # Check if referenced by TRIALS.md rollback
        trials_text = read_text(WORKSPACE / "TRIALS.md")
        if f.name in trials_text:
            find(
                "INFO", str(f.relative_to(WORKSPACE)), 0,
                f"Backup file referenced by TRIALS.md rollback instructions",
                "Kept for rollback safety",
                "Remove after all trials are resolved (post-2026-05-07)",
            )
        else:
            find(
                "WARNING", str(f.relative_to(WORKSPACE)), 0,
                f"Orphaned backup file: {f.name}",
                "No active process references this backup",
                "Delete if no longer needed",
            )

    # Orphaned markdown files in workspace root
    for f in WORKSPACE.glob("*.md"):
        if f.name not in CORE_FILES:
            find(
                "INFO", str(f.relative_to(WORKSPACE)), 0,
                f"Non-core markdown file in workspace root: {f.name}",
                "Not listed as a core tracker file",
                "Archive to memory/archive/ or add to CORE_FILES if it belongs",
            )


# ── 6. Cron / Skill mismatches ─────────────────────────────────────────
def load_cron_jobs() -> dict:
    try:
        return json.loads(CRON_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_cron_skill_mismatch():
    cron_data = load_cron_jobs()
    if not cron_data:
        find("CRITICAL", "cron/jobs.json", 0, "Cannot read cron jobs", "File missing or unreadable", "Investigate cron system health")
        return

    jobs = cron_data.get("jobs", [])
    job_names = {j.get("name", ""): j for j in jobs}
    job_ids = {j.get("id", ""): j for j in jobs}

    # Check for skills with no cron registration
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_name = skill_dir.name
        # Check if any cron job references this skill
        referenced = any(
            skill_name.replace("-", " ") in j.get("name", "").lower()
            or skill_name in j.get("payload", {}).get("message", "")
            for j in jobs
        )
        if not referenced:
            find(
                "INFO", f"skills/{skill_name}/", 0,
                f"Skill '{skill_name}' has no registered cron job",
                "Skill exists but is not triggered automatically",
                "Register a cron job if the skill should run on schedule, or document as on-demand",
            )

    # Removed: 6-field "invalid" check. OpenClaw's cron parser accepts both
    # 5-field and quartz-style 6-field (seconds-first) expressions, so this
    # was producing false-positive CRITICAL findings on working jobs.

    # Removed: "never ran" check. It read `state.lastRun` from jobs.json, but
    # OpenClaw doesn't persist last-run there — every job has `state: {}`.
    # Actual execution history lives in gateway runtime state; surface it with
    # `openclaw cron list` (the "Last" column) if this check is ever restored.

    # Check PROJECTS.md entries against actual cron jobs
    proj_text = read_text(WORKSPACE / "PROJECTS.md")
    for match in re.finditer(r'## ([^\n]+)', proj_text):
        title = match.group(1).strip()
        # Look for cron-like references in the entry
        entry_start = match.start()
        next_heading = proj_text.find("## ", entry_start + 1)
        entry = proj_text[entry_start:next_heading if next_heading != -1 else len(proj_text)]

        # If entry claims "awaiting first run" or "active", verify cron exists
        # Skip on-demand skills (pdf-export, social-feed-monitor when manual)
        on_demand_keywords = ["pdf", "on demand", "on-demand", "manual", "skill integration test"]
        if any(kw in entry.lower() for kw in on_demand_keywords):
            continue
        if "awaiting first run" in entry.lower() or "implementation complete" in entry.lower():
            # Try to find a matching cron job
            found = any(title.lower() in j.get("name", "").lower() for j in jobs)
            if not found:
                find(
                    "CRITICAL", "PROJECTS.md", entry_start,
                    f"Project '{title}' claims implementation complete/awaiting run but no matching cron job found",
                    "Cron job may have been deleted or never created",
                    "Verify the cron job exists or update the project status",
                )


# ── 7. Daily log contradictions ────────────────────────────────────────
def check_daily_logs():
    today = datetime.now().strftime("%Y-%m-%d")
    today_file = MEMORY_DIR / f"{today}.md"
    if not today_file.exists():
        find(
            "WARNING", f"memory/{today}.md", 0,
            "Today's daily memory file does not exist",
            "ensure-daily-memory hook may have failed",
            "Check hook status and create the file if needed",
        )


# ── 8. DREAMS.md / dreaming cron drift ─────────────────────────────────
def check_dreams():
    cron_data = load_cron_jobs()
    if not cron_data:
        return

    dreaming_job = None
    for job in cron_data.get("jobs", []):
        if "dream" in job.get("name", "").lower():
            dreaming_job = job
            break

    if dreaming_job:
        if "delivery" not in dreaming_job or not dreaming_job.get("delivery"):
            find(
                "WARNING", "cron/jobs.json", 0,
                f"Dreaming cron '{dreaming_job.get('name')}' has no delivery block",
                "Output goes to memory/dreaming/ but not to DREAMS.md or Telegram",
                "Add delivery config or archive DREAMS.md if it's no longer used",
            )

    dreams_text = read_text(WORKSPACE / "DREAMS.md")
    if dreams_text and "openclaw:dreaming:diary:start" in dreams_text:
        # Check if content matches technical dreaming logs
        dreaming_dir = MEMORY_DIR / "dreaming"
        if dreaming_dir.exists():
            # DREAMS.md has poetic content; technical logs are in memory/dreaming/
            # This is acceptable drift — just note it
            find(
                "INFO", "DREAMS.md", 0,
                "DREAMS.md contains poetic content while dreaming cron writes technical logs to memory/dreaming/",
                "Two different formats for the same subsystem",
                "Decide if DREAMS.md is the canonical diary or if it should be archived",
            )


# ── Report formatting ────────────────────────────────────────────────────
def print_report():
    sev_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    FINDINGS.sort(key=lambda f: (sev_order.get(f["severity"], 99), f["source"]))

    critical = [f for f in FINDINGS if f["severity"] == "CRITICAL"]
    warnings = [f for f in FINDINGS if f["severity"] == "WARNING"]
    info = [f for f in FINDINGS if f["severity"] == "INFO"]

    print("🧭 Drift Audit Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"Workspace: {WORKSPACE}")
    print("")

    if not FINDINGS:
        print("🧭 Drift audit clean. No issues found.")
        return

    print(f"Summary: {len(critical)} critical, {len(warnings)} warnings, {len(info)} info")
    print("")

    for f in FINDINGS:
        icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🟢"}.get(f["severity"], "⚪")
        print(f"{icon} [{f['severity']}] {f['source']}")
        if f["line"]:
            print(f"   Line: {f['line']}")
        print(f"   Claim: {f['claim']}")
        print(f"   Reality: {f['reality']}")
        print(f"   Fix: {f['fix']}")
        print("")

    # Append daily log summary unless explicitly disabled.
    if ARGS and ARGS.no_log:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    daily_file = MEMORY_DIR / f"{today}.md"
    if daily_file.exists():
        entry = (
            f"\n## Drift Audit — {datetime.now().strftime('%H:%M')}\n"
            f"- {len(critical)} critical findings\n"
            f"- {len(warnings)} warnings\n"
            f"- {len(info)} info notes\n"
            f"- Top issue: {critical[0]['claim'] if critical else (warnings[0]['claim'] if warnings else 'None')}\n"
        )
        try:
            with open(daily_file, "a", encoding="utf-8") as fh:
                fh.write(entry)
        except Exception as e:
            print(f"⚠️ Could not append to daily log: {e}")


# ── Main ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ARGS = parse_args()
    check_projects_md()
    check_memory_md()
    check_heartbeat_md()
    check_trials_md()
    check_orphaned_files()
    check_cron_skill_mismatch()
    check_daily_logs()
    check_dreams()
    print_report()
    sys.exit(0 if not any(f["severity"] == "CRITICAL" for f in FINDINGS) else 1)
