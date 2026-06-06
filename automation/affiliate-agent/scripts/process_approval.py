"""
Process APPROVE or REJECT commands for pending articles.

  APPROVE → moves pending/{slug}.json to approved/{slug}.json
  REJECT  → moves pending/{slug}.json to rejected/{slug}.json

The status and processed_at fields are updated in the JSON file.

Usage:
    python process_approval.py APPROVE:{slug} [--dry-run]
    python process_approval.py REJECT:{slug}  [--dry-run]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import PENDING_DIR, APPROVED_DIR, REJECTED_DIR, log_action

_VALID_ACTIONS = {"APPROVE", "REJECT"}


def process_approval(command: str, dry_run: bool = False) -> dict:
    """
    Parse and execute an APPROVE or REJECT command.

    Returns a result dict with keys: success, slug, action, dest (or error).
    """
    command = command.strip()
    if ":" not in command:
        return {
            "success": False,
            "error": f"Invalid format '{command}'. Expected APPROVE:{{slug}} or REJECT:{{slug}}.",
        }

    action, slug = command.split(":", 1)
    action = action.upper().strip()
    slug   = slug.strip()

    if action not in _VALID_ACTIONS:
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Must be APPROVE or REJECT.",
        }

    pending_file = PENDING_DIR / f"{slug}.json"
    if not pending_file.exists():
        return {
            "success": False,
            "error": f"No pending approval found for slug '{slug}'.",
        }

    approval = json.loads(pending_file.read_text(encoding="utf-8"))

    if action == "APPROVE":
        dest_dir   = APPROVED_DIR
        new_status = "APPROVED"
    else:
        dest_dir   = REJECTED_DIR
        new_status = "REJECTED"

    approval["status"]       = new_status
    approval["processed_at"] = datetime.now(timezone.utc).isoformat()

    dest_file = dest_dir / f"{slug}.json"
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(
            json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        pending_file.unlink()

    log_action(slug, f"process_{new_status.lower()}", str(dest_file), dry_run)
    return {
        "success": True,
        "slug":    slug,
        "action":  new_status,
        "dest":    str(dest_file),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Move a pending approval to approved or rejected"
    )
    parser.add_argument("command",
                        help="APPROVE:{slug} or REJECT:{slug}")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only — no files moved or modified")
    args = parser.parse_args()

    result = process_approval(args.command, dry_run=args.dry_run)

    if result["success"]:
        prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"{prefix}[OK] {result['action']}: {result['slug']}")
        if not args.dry_run:
            print(f"  -> {result['dest']}")
    else:
        print(f"[FAIL] Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("\n[DRY-RUN] No files were moved or modified.")


if __name__ == "__main__":
    main()
