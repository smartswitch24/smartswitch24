"""
OpenClaw Telegram Watcher — runs on the Raspberry Pi after git pull.

Detects new pending approval requests and sends Telegram preview messages.
Processes APPROVE / REJECT commands from the CLI.
Polls Telegram for incoming commands and dispatches them to the pipeline.

Usage:
    python openclaw_telegram_watcher.py --send-pending [--dry-run]
    python openclaw_telegram_watcher.py --process-command APPROVE:{slug} [--dry-run]
    python openclaw_telegram_watcher.py --poll-updates [--dry-run]

Required environment variables (not needed for --dry-run):
    TELEGRAM_BOT_TOKEN   Bot token from @BotFather
    TELEGRAM_CHAT_ID     Your personal or group chat ID

Supported Telegram commands (sent via chat to the bot):
    STATUS               Show pipeline counts and slug lists
    APPROVE:{slug}       Move pending -> approved, run publish dry-run, report result
    REJECT:{slug}        Move pending -> rejected, confirm via Telegram
    PUBLISH:{slug}       Publish an APPROVED article: commit, push, deploy
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
from utils import (
    AGENT_DIR, APPROVED_DIR, LOGS_DIR, PENDING_DIR, REJECTED_DIR, TELEGRAM_DIR,
)

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPTS_DIR   = Path(__file__).resolve().parent
DATA_DIR      = AGENT_DIR / "data"
SENT_STATE    = DATA_DIR / "telegram_sent.json"
UPDATES_STATE = DATA_DIR / "telegram_updates.json"
WATCHER_LOG   = LOGS_DIR / "telegram-watcher.log"


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


def _load_updates_state() -> dict:
    if UPDATES_STATE.exists():
        try:
            return json.loads(UPDATES_STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_updates_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_STATE.write_text(
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


def _get_telegram_updates(token: str, offset: int) -> list:
    """Fetch pending updates from Telegram Bot API getUpdates (non-blocking)."""
    url = (
        f"https://api.telegram.org/bot{token}/getUpdates"
        f"?offset={offset}&timeout=0&limit=100"
    )
    try:
        with urllib_request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data.get("result", [])
            print(f"[ERROR] Telegram getUpdates not ok: {data}", file=sys.stderr)
            return []
    except urllib_error.HTTPError as exc:
        print(f"[ERROR] Telegram getUpdates {exc.code}: {exc.reason}", file=sys.stderr)
        return []
    except urllib_error.URLError as exc:
        print(f"[ERROR] Telegram getUpdates connection failed: {exc.reason}", file=sys.stderr)
        return []
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ERROR] Telegram getUpdates parse error: {exc}", file=sys.stderr)
        return []


# ── Pipeline status helpers ───────────────────────────────────────────────────
def _slugs_by_status(directory: Path, expected_status: str) -> list:
    """Return sorted stems of JSON files in directory whose status matches."""
    if not directory.exists():
        return []
    results = []
    for f in sorted(directory.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == expected_status:
                results.append(f.stem)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _build_status_message() -> str:
    pending   = _slugs_by_status(PENDING_DIR,  "PENDING")
    approved  = _slugs_by_status(APPROVED_DIR, "APPROVED")
    rejected  = _slugs_by_status(REJECTED_DIR, "REJECTED")
    published = _slugs_by_status(APPROVED_DIR, "PUBLISHED")

    lines = [
        "SmartSwitch24 Pipeline Status",
        "",
        f"Pending:   {len(pending)}",
        f"Approved:  {len(approved)}  (ready to PUBLISH)",
        f"Rejected:  {len(rejected)}",
        f"Published: {len(published)}",
    ]
    if pending:
        lines.append("\nAwaiting decision:")
        for s in pending:
            lines.append(f"  {s}")
        lines.append("\nApprove:  APPROVE:{slug}")
        lines.append("Reject:   REJECT:{slug}")
    if approved:
        lines.append("\nReady to publish:")
        for s in approved:
            lines.append(f"  {s}")
        lines.append("\nPublish:  PUBLISH:{slug}")
    if not pending and not approved:
        lines.append("\nNothing pending or ready to publish.")
    return "\n".join(lines)


# ── Telegram command handlers ─────────────────────────────────────────────────
def _handle_status(token: str, chat_id: str) -> None:
    msg = _build_status_message()
    _log("*", "poll_status", "OK")
    _send_telegram_message(msg, token, chat_id)


def _handle_approve(slug: str, token: str, chat_id: str) -> None:
    # Step 1: move pending → approved
    process_script = SCRIPTS_DIR / "process_approval.py"
    p1 = subprocess.run(
        [sys.executable, str(process_script), f"APPROVE:{slug}"],
        capture_output=True, text=True,
    )
    approval_ok = p1.returncode == 0
    _log(
        slug, "poll_approve",
        "OK" if approval_ok else f"FAILED: {(p1.stderr or '').strip()[:120]}",
    )

    if not approval_ok:
        _send_telegram_message(
            f"APPROVE:{slug}\n"
            f"FAILED\n"
            f"{(p1.stderr or p1.stdout or 'unknown error').strip()[:300]}",
            token, chat_id,
        )
        return

    # Step 2: publish dry-run to validate before PUBLISH command
    publish_script = SCRIPTS_DIR / "publish_article_pair.py"
    p2 = subprocess.run(
        [sys.executable, str(publish_script), "--dry-run", "--slug", slug],
        capture_output=True, text=True,
    )
    publish_output = (p2.stdout or p2.stderr or "").strip()
    publish_ok     = p2.returncode == 0
    _log(slug, "poll_dry_run_publish", "PASSED" if publish_ok else f"ISSUES: {publish_output[:120]}")

    if publish_ok:
        _send_telegram_message(
            f"APPROVE:{slug}\n"
            f"Approved. Moved to approved/.\n"
            f"Publish dry-run: PASSED\n\n"
            f"Ready. Send to publish:\n"
            f"PUBLISH:{slug}",
            token, chat_id,
        )
    else:
        _send_telegram_message(
            f"APPROVE:{slug}\n"
            f"Approved. Moved to approved/.\n"
            f"Publish dry-run: ISSUES FOUND\n\n"
            f"{publish_output[:400]}\n\n"
            f"Fix issues before sending PUBLISH:{slug}",
            token, chat_id,
        )


def _handle_reject(slug: str, token: str, chat_id: str) -> None:
    process_script = SCRIPTS_DIR / "process_approval.py"
    p = subprocess.run(
        [sys.executable, str(process_script), f"REJECT:{slug}"],
        capture_output=True, text=True,
    )
    ok = p.returncode == 0
    _log(
        slug, "poll_reject",
        "OK" if ok else f"FAILED: {(p.stderr or '').strip()[:120]}",
    )
    if ok:
        _send_telegram_message(
            f"REJECT:{slug}\n"
            f"Rejected. Moved to rejected/.",
            token, chat_id,
        )
    else:
        _send_telegram_message(
            f"REJECT:{slug}\n"
            f"FAILED: {(p.stderr or p.stdout or 'unknown error').strip()[:300]}",
            token, chat_id,
        )


def _handle_publish(slug: str, token: str, chat_id: str) -> None:
    # Safety gate: approved JSON must exist with status APPROVED
    approved_json = APPROVED_DIR / f"{slug}.json"
    if not approved_json.exists():
        _log(slug, "poll_publish", "BLOCKED: no approved JSON")
        _send_telegram_message(
            f"PUBLISH:{slug}\n"
            f"BLOCKED: No approved JSON found.\n"
            f"Run APPROVE:{slug} first.",
            token, chat_id,
        )
        return

    try:
        approval_data = json.loads(approved_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log(slug, "poll_publish", f"BLOCKED: JSON read error: {exc}")
        _send_telegram_message(
            f"PUBLISH:{slug}\n"
            f"BLOCKED: Could not read approval JSON.",
            token, chat_id,
        )
        return

    current_status = approval_data.get("status", "unknown")
    if current_status != "APPROVED":
        _log(slug, "poll_publish", f"BLOCKED: status={current_status}")
        _send_telegram_message(
            f"PUBLISH:{slug}\n"
            f"BLOCKED: Status is {current_status}, not APPROVED.\n"
            f"Only APPROVED articles can be published.",
            token, chat_id,
        )
        return

    # Real publish: commit + push
    publish_script = SCRIPTS_DIR / "publish_article_pair.py"
    p = subprocess.run(
        [sys.executable, str(publish_script), "--slug", slug],
        capture_output=True, text=True,
    )
    output = (p.stdout or p.stderr or "").strip()
    ok     = p.returncode == 0
    _log(slug, "poll_publish", "PUBLISHED" if ok else f"FAILED: {output[:120]}")

    if ok:
        _send_telegram_message(
            f"PUBLISH:{slug}\n"
            f"Published!\n"
            f"Committed and pushed to GitHub.\n"
            f"Cloudflare deploy triggered automatically.",
            token, chat_id,
        )
    else:
        _send_telegram_message(
            f"PUBLISH:{slug}\n"
            f"FAILED:\n{output[:400]}",
            token, chat_id,
        )


# ── Command dispatch ──────────────────────────────────────────────────────────
def _dispatch_text(text: str, token: str, chat_id: str) -> bool:
    """
    Parse and dispatch a single Telegram message text.
    Returns True if recognized and handled, False if unknown.
    Command prefix is case-insensitive; slug is preserved as-is.
    """
    stripped = text.strip()
    upper    = stripped.upper()

    if upper == "STATUS":
        _handle_status(token, chat_id)
        return True

    if upper.startswith("APPROVE:"):
        slug = stripped[len("APPROVE:"):].strip()
        if slug:
            _handle_approve(slug, token, chat_id)
            return True

    if upper.startswith("REJECT:"):
        slug = stripped[len("REJECT:"):].strip()
        if slug:
            _handle_reject(slug, token, chat_id)
            return True

    if upper.startswith("PUBLISH:"):
        slug = stripped[len("PUBLISH:"):].strip()
        if slug:
            _handle_publish(slug, token, chat_id)
            return True

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


# ── --poll-updates ────────────────────────────────────────────────────────────
def cmd_poll_updates(dry_run: bool) -> None:
    """
    Fetch new Telegram messages via getUpdates (short-poll, non-blocking).

    Security:
      - Messages from any chat_id other than TELEGRAM_CHAT_ID are logged and dropped.
      - No credentials are logged.

    State:
      - data/telegram_updates.json tracks last_update_id.
      - Offset is advanced after every run so updates are never processed twice.

    In dry-run mode: no API call is made, no state is modified.
    """
    if dry_run:
        print("[DRY-RUN] --poll-updates: would call getUpdates with stored offset.")
        print("[DRY-RUN] No API call made. No state modified.")
        _log("*", "poll_updates", "[DRY-RUN] WOULD_POLL")
        return

    token, chat_id = _require_env()

    updates_state  = _load_updates_state()
    last_update_id = updates_state.get("last_update_id", 0)
    offset         = last_update_id + 1 if last_update_id else 0

    updates = _get_telegram_updates(token, offset)

    if not updates:
        print("No new Telegram updates.")
        return

    print(f"Fetched {len(updates)} update(s).")
    new_last_id = last_update_id

    for update in updates:
        update_id   = update.get("update_id", 0)
        new_last_id = max(new_last_id, update_id)

        # Accept both new messages and edited messages
        message   = update.get("message") or update.get("edited_message") or {}
        from_chat = message.get("chat", {})
        from_id   = str(from_chat.get("id", "")).strip()
        text      = (message.get("text") or "").strip()

        # Security: silently drop unauthorized senders; never log the token
        if from_id != chat_id:
            _log("*", "poll_updates",
                 f"UNAUTHORIZED update_id={update_id} from_id={from_id}")
            continue

        if not text:
            _log("*", "poll_updates",
                 f"IGNORED empty message update_id={update_id}")
            continue

        print(f"  [CMD] update_id={update_id}  text='{text}'")
        recognized = _dispatch_text(text, token, chat_id)

        if not recognized:
            _log("*", "poll_updates",
                 f"UNRECOGNIZED '{text[:80]}' update_id={update_id}")
            _send_telegram_message(
                f"Unknown command: '{text}'\n\n"
                "Available commands:\n"
                "  STATUS\n"
                "  APPROVE:{slug}\n"
                "  REJECT:{slug}\n"
                "  PUBLISH:{slug}",
                token, chat_id,
            )

    # Advance offset — prevents any update in this batch from being seen again
    _save_updates_state({
        "last_update_id": new_last_id,
        "processed_at":   datetime.now(timezone.utc).isoformat(),
    })
    print(f"State saved. last_update_id={new_last_id}")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenClaw Telegram Watcher — SmartSwitch24 approval pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Preview what would be sent (no credentials needed)\n"
            "  python openclaw_telegram_watcher.py --send-pending --dry-run\n\n"
            "  # Send all unsent pending previews to Telegram\n"
            "  python openclaw_telegram_watcher.py --send-pending\n\n"
            "  # Approve a slug (moves to approved/, runs publish dry-run)\n"
            "  python openclaw_telegram_watcher.py --process-command APPROVE:mallorca-oder-tuerkei\n\n"
            "  # Reject a slug\n"
            "  python openclaw_telegram_watcher.py --process-command REJECT:mallorca-oder-tuerkei\n\n"
            "  # Poll Telegram for STATUS / APPROVE / REJECT / PUBLISH commands\n"
            "  python openclaw_telegram_watcher.py --poll-updates\n\n"
            "  # Dry-run poll (no API call, no state change)\n"
            "  python openclaw_telegram_watcher.py --poll-updates --dry-run\n"
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
        help="Process APPROVE:{slug} or REJECT:{slug} from the CLI",
    )
    mode.add_argument(
        "--poll-updates",
        action="store_true",
        help=(
            "Fetch new Telegram messages and dispatch recognized pipeline commands "
            "(STATUS, APPROVE, REJECT, PUBLISH)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Preview only — no messages sent, no files modified, no git actions. "
            "Telegram credentials not required (except --poll-updates live run)."
        ),
    )

    args = parser.parse_args()

    if args.send_pending:
        cmd_send_pending(dry_run=args.dry_run)
    elif args.poll_updates:
        cmd_poll_updates(dry_run=args.dry_run)
    else:
        cmd_process_command(args.process_command, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
