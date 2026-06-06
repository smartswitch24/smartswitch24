"""
OpenClaw Telegram Watcher — runs on the Raspberry Pi after git pull.

Detects new pending approval requests and sends Telegram preview messages.
Processes APPROVE / REJECT commands from the CLI.

Usage:
    python openclaw_telegram_watcher.py --send-pending [--dry-run]
    python openclaw_telegram_watcher.py --process-command APPROVE:{slug} [--dry-run]

Required environment variables (not needed for --dry-run):
    TELEGRAM_BOT_TOKEN   Bot token from @BotFather
    TELEGRAM_CHAT_ID     Your personal or group chat ID
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

# Ensure UTF-8 output on Windows dev machines (Pi uses UTF-8 by default)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from utils import AGENT_DIR, LOGS_DIR, PENDING_DIR, TELEGRAM_DIR

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent
DATA_DIR    = AGENT_DIR / "data"
SENT_STATE  = DATA_DIR / "telegram_sent.json"
WATCHER_LOG = LOGS_DIR / "telegram-watcher.log"


# ── Logging ──────────────────────────────────────────────────────────────────
def _log(slug: str, action: str, result: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} | {slug} | {action} | {result}\n"
    with WATCHER_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line.rstrip())


# ── State tracking ───────────────────────────────────────────────────────────
def _load_sent_state() -> dict:
    if SENT_STATE.exists():
        try:
            return json.loads(SENT_STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_sent_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SENT_STATE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Environment ──────────────────────────────────────────────────────────────
def _require_env() -> tuple:
    """Return (token, chat_id) or exit with a clear error if either is missing."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    missing = [v for v, val in (
        ("TELEGRAM_BOT_TOKEN", token),
        ("TELEGRAM_CHAT_ID",   chat_id),
    ) if not val]
    if missing:
        for var in missing:
            print(f"[ERROR] Environment variable not set: {var}", file=sys.stderr)
        print(
            "\nSet them before running:\n"
            "  export TELEGRAM_BOT_TOKEN=your_token\n"
            "  export TELEGRAM_CHAT_ID=your_chat_id",
            file=sys.stderr,
        )
        sys.exit(1)
    return token, chat_id


# ── Telegram API ─────────────────────────────────────────────────────────────
def _send_telegram_message(text: str, token: str, chat_id: str) -> bool:
    """POST a plain-text message to Telegram Bot API. Returns True on success."""
    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req     = urllib_request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except urllib_error.HTTPError as exc:
        print(f"[ERROR] Telegram API {exc.code}: {exc.reason}", file=sys.stderr)
        return False
    except urllib_error.URLError as exc:
        print(f"[ERROR] Telegram connection failed: {exc.reason}", file=sys.stderr)
        return False


# ── --send-pending ────────────────────────────────────────────────────────────
def cmd_send_pending(dry_run: bool) -> None:
    """
    For each pending approval that has not yet been sent:
      1. Read telegram/{slug}.md
      2. Send to Telegram
      3. Record in telegram_sent.json

    In dry-run mode: previews messages to stdout, does not send or modify state.
    """
    token = chat_id = ""
    if not dry_run:
        token, chat_id = _require_env()

    state = _load_sent_state()

    if not PENDING_DIR.exists():
        print("No pending approvals directory found.")
        return

    pending = sorted(PENDING_DIR.glob("*.json"))
    if not pending:
        print("No pending approval requests found.")
        return

    sent = 0
    for json_file in pending:
        slug = json_file.stem

        if state.get(slug, {}).get("telegram_message_sent"):
            print(f"  [SKIP] Already sent: {slug}")
            continue

        preview_file = TELEGRAM_DIR / f"{slug}.md"
        if not preview_file.exists():
            _log(slug, "send_telegram", f"SKIP — preview missing: {preview_file.name}")
            continue

        text = preview_file.read_text(encoding="utf-8").strip()

        if dry_run:
            print(f"\n[DRY-RUN] Would send: {slug}")
            print("-" * 40)
            print(text)
            print("-" * 40)
            _log(slug, "send_telegram", "[DRY-RUN] WOULD_SEND")
        else:
            print(f"  Sending: {slug} ...")
            ok = _send_telegram_message(text, token, chat_id)
            if ok:
                state[slug] = {
                    "sent_at":               datetime.now(timezone.utc).isoformat(),
                    "telegram_message_sent": True,
                }
                _save_sent_state(state)
                _log(slug, "send_telegram", "SENT")
                sent += 1
            else:
                _log(slug, "send_telegram", "SEND_FAILED")

    if dry_run:
        print("\n[DRY-RUN] No messages sent. No state modified.")
    else:
        print(f"\nDone. {sent} message(s) sent.")


# ── --process-command ─────────────────────────────────────────────────────────
def cmd_process_command(command: str, dry_run: bool) -> None:
    """
    Handle APPROVE:{slug} or REJECT:{slug}.

    On APPROVE (real run):
      1. Call process_approval.py APPROVE:{slug}        — moves pending → approved
      2. Call publish_article_pair.py --dry-run --slug  — validates, does not publish
      3. Print instructions for manual publish step

    On APPROVE --dry-run:
      1. Call process_approval.py APPROVE:{slug} --dry-run  — preview only
      2. Skip publish dry-run (approval file was not moved)
      3. Explain what a real run would do

    On REJECT (real or dry-run):
      1. Call process_approval.py REJECT:{slug} [--dry-run]
    """
    command = command.strip()

    if ":" not in command:
        print(
            f"[ERROR] Invalid format: '{command}'. "
            "Expected APPROVE:{{slug}} or REJECT:{{slug}}.",
            file=sys.stderr,
        )
        sys.exit(1)

    action, slug = command.split(":", 1)
    action = action.upper().strip()
    slug   = slug.strip()

    if action not in ("APPROVE", "REJECT"):
        print(
            f"[ERROR] Unknown action '{action}'. Must be APPROVE or REJECT.",
            file=sys.stderr,
        )
        sys.exit(1)

    full_command = f"{action}:{slug}"
    dry_flag     = ["--dry-run"] if dry_run else []

    # ── Step 1: process_approval.py ──────────────────────────────────────────
    process_script = SCRIPTS_DIR / "process_approval.py"
    p1 = subprocess.run(
        [sys.executable, str(process_script), full_command] + dry_flag,
        capture_output=True, text=True,
    )
    print(p1.stdout.strip())

    if p1.returncode != 0:
        msg = (p1.stderr or "unknown error").strip()
        print(f"[FAIL] process_approval.py: {msg}", file=sys.stderr)
        _log(slug, f"process_{action.lower()}", f"FAILED: {msg}")
        sys.exit(1)

    _log(slug, f"process_{action.lower()}", "[DRY-RUN] OK" if dry_run else "OK")

    # ── Step 2: APPROVE → publish dry-run ────────────────────────────────────
    if action == "APPROVE":
        if dry_run:
            print(
                "\n[DRY-RUN] Publish dry-run skipped — "
                "approval file was not moved (no real state changed)."
            )
            print(
                "\n  A real run (without --dry-run) would:\n"
                f"  1. Move  approvals/pending/{slug}.json  →  approvals/approved/\n"
                f"  2. Run   publish_article_pair.py --dry-run --slug {slug}\n"
                f"  3. Report dry-run result and give you the manual publish command."
            )
            _log(slug, "dry_run_publish", "[DRY-RUN] SKIPPED")
        else:
            publish_script = SCRIPTS_DIR / "publish_article_pair.py"
            p2 = subprocess.run(
                [sys.executable, str(publish_script), "--dry-run", "--slug", slug],
                capture_output=True, text=True,
            )
            output = (p2.stdout or p2.stderr or "").strip()
            print("\n--- Publish dry-run output ---")
            print(output)
            print("------------------------------")

            if p2.returncode != 0:
                _log(slug, "dry_run_publish", f"ISSUES: {output[:200]}")
                print(f"\n[WARN] Publish dry-run reported issues for: {slug}")
                print("       Resolve issues before publishing manually.")
            else:
                _log(slug, "dry_run_publish", "PASSED")
                print(f"\n[OK] Dry-run passed for: {slug}")
                print("     Real publishing is manual. Run when ready:")
                print(
                    f"\n     python automation/affiliate-agent/scripts/"
                    f"publish_article_pair.py --slug {slug}"
                )


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenClaw Telegram Watcher — SmartSwitch24 approval pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Preview what would be sent (no Telegram credentials needed)\n"
            "  python openclaw_telegram_watcher.py --send-pending --dry-run\n\n"
            "  # Send all unsent pending previews to Telegram\n"
            "  python openclaw_telegram_watcher.py --send-pending\n\n"
            "  # Approve a slug (moves to approved/, runs publish dry-run)\n"
            "  python openclaw_telegram_watcher.py --process-command APPROVE:griechenland-pauschalreisen-2026\n\n"
            "  # Reject a slug\n"
            "  python openclaw_telegram_watcher.py --process-command REJECT:griechenland-pauschalreisen-2026\n\n"
            "  # Dry-run any command\n"
            "  python openclaw_telegram_watcher.py --process-command APPROVE:griechenland-pauschalreisen-2026 --dry-run\n"
        ),
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--send-pending",
        action="store_true",
        help="Send Telegram previews for all unsent pending approvals",
    )
    mode.add_argument(
        "--process-command",
        metavar="CMD",
        help="Process APPROVE:{slug} or REJECT:{slug}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Preview only — no messages sent, no files modified, no git actions. "
            "Telegram credentials not required."
        ),
    )

    args = parser.parse_args()

    if args.send_pending:
        cmd_send_pending(dry_run=args.dry_run)
    else:
        cmd_process_command(args.process_command, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
