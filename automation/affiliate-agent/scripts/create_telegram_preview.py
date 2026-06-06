"""
Generate Telegram preview markdown files for pending approval requests.

Output: automation/affiliate-agent/telegram/{slug}.md

The preview file contains:
  - Article summary (German + Arabic titles)
  - Image check results
  - APPROVE / REJECT commands for OpenClaw

Usage:
    python create_telegram_preview.py [--dry-run] [--slug SLUG]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import PENDING_DIR, TELEGRAM_DIR, image_exists, log_action


def _image_line(ref: str) -> str:
    mark = "✔" if image_exists(ref) else "✗"
    return f"{mark} {Path(ref).name}"


def build_preview(approval: dict) -> str:
    slug     = approval["slug"]
    de_title = approval.get("german_title", slug)
    ar_title = approval.get("arabic_title", slug)
    images   = approval.get("images", [])

    images_block = (
        "\n".join(_image_line(img) for img in images)
        if images else "(no images referenced)"
    )
    images_ok = all(image_exists(img) for img in images)

    return (
        f"🏖 SmartSwitch24 Draft Ready\n\n"
        f"German:\n{de_title}\n\n"
        f"Arabic:\n{ar_title}\n\n"
        f"Images:\n{images_block}\n\n"
        f"Checks:\n"
        f"✔ German Draft\n"
        f"✔ Arabic Draft\n"
        f"{'✔' if images_ok else '✗'} Images\n\n"
        f"---\n\n"
        f"APPROVE:{slug}\n\n"
        f"REJECT:{slug}\n"
    )


def create_telegram_preview(approval: dict, dry_run: bool = False) -> str:
    slug    = approval["slug"]
    preview = build_preview(approval)

    output_path = TELEGRAM_DIR / f"{slug}.md"
    if not dry_run:
        TELEGRAM_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(preview, encoding="utf-8")
    log_action(slug, "create_telegram_preview", str(output_path), dry_run)
    return preview


def main():
    parser = argparse.ArgumentParser(
        description="Generate Telegram preview files for pending approval requests"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only — no files created or modified")
    parser.add_argument("--slug", metavar="SLUG",
                        help="Process only this specific slug")
    args = parser.parse_args()

    if not PENDING_DIR.exists():
        print("No pending approvals directory found.")
        return

    pending_files = sorted(PENDING_DIR.glob("*.json"))
    if not pending_files:
        print("No pending approval requests found.")
        return

    if args.slug:
        pending_files = [f for f in pending_files if f.stem == args.slug]
        if not pending_files:
            print(f"No pending approval found for slug '{args.slug}'.")
            sys.exit(1)

    for json_file in pending_files:
        approval = json.loads(json_file.read_text(encoding="utf-8"))
        slug     = approval["slug"]
        print(f"\nGenerating preview: {slug}")
        preview  = create_telegram_preview(approval, dry_run=args.dry_run)
        if args.dry_run:
            print("─" * 40)
            print(preview)
            print("─" * 40)
        else:
            print(f"  [OK] Saved: automation/affiliate-agent/telegram/{slug}.md")

    if args.dry_run:
        print("\n[DRY-RUN] No files were created or modified.")


if __name__ == "__main__":
    main()
