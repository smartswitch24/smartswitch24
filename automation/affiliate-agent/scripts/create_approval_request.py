"""
Create approval request JSON files for valid draft pairs.

Checks performed per pair:
  1. Images exist in public/Images/
  2. No duplicate slug or similar title in published blog

On success  → automation/affiliate-agent/approvals/pending/{slug}.json
On failure  → automation/affiliate-agent/reports/{missing-images|duplicate}-{slug}.md

Usage:
    python create_approval_request.py [--dry-run] [--slug SLUG]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    REPO_ROOT, PENDING_DIR, REPORTS_DIR,
    find_draft_pairs, parse_frontmatter,
    get_frontmatter_images, image_exists,
    check_duplicate, log_action,
)


def _relative(path: Path) -> str:
    """Forward-slash path relative to repo root (safe across OS)."""
    return path.relative_to(REPO_ROOT).as_posix()


def _collect_images(de_path: Path, ar_path: Path) -> list:
    images = []
    for p in (de_path, ar_path):
        for ref in get_frontmatter_images(parse_frontmatter(p)):
            if ref not in images:
                images.append(ref)
    return images


def create_approval_request(pair: dict, dry_run: bool = False) -> dict:
    slug    = pair["slug"]
    de_path = pair["de_path"]
    ar_path = pair["ar_path"]

    de_fm = parse_frontmatter(de_path)
    ar_fm = parse_frontmatter(ar_path)

    de_title = de_fm.get("title", slug)
    ar_title = ar_fm.get("title", slug)
    images   = _collect_images(de_path, ar_path)

    # ------------------------------------------------------------------ images
    missing = [img for img in images if not image_exists(img)]
    if missing:
        report = (
            f"# Missing Images Report: {slug}\n\n"
            f"Status: NEEDS_IMAGES\n\n"
            f"Slug: {slug}\n"
            f"German Title: {de_title}\n"
            f"Arabic Title: {ar_title}\n"
            f"Date: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"## Missing Images\n\n"
            + "\n".join(f"- `{img}`" for img in missing)
            + "\n\n## Action Required\n\n"
            "Add the missing images to `public/Images/` before creating an approval request.\n"
        )
        if not dry_run:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            (REPORTS_DIR / f"missing-images-{slug}.md").write_text(report, encoding="utf-8")
        log_action(slug, "create_approval_request", f"NEEDS_IMAGES: {missing}", dry_run)
        return {"slug": slug, "status": "NEEDS_IMAGES", "missing_images": missing}

    # --------------------------------------------------------------- duplicates
    dup = check_duplicate(slug, de_title, ar_title)
    if dup["is_duplicate"]:
        report = (
            f"# Duplicate Detection Report: {slug}\n\n"
            f"Status: DUPLICATE_FOUND\n\n"
            f"Slug: {slug}\n"
            f"German Title: {de_title}\n"
            f"Arabic Title: {ar_title}\n"
            f"Date: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"## Reason\n\n{dup['reason']}\n\n"
            "## Action Required\n\nDo not publish. Resolve the duplicate manually.\n"
        )
        if not dry_run:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            (REPORTS_DIR / f"duplicate-{slug}.md").write_text(report, encoding="utf-8")
        log_action(slug, "create_approval_request", f"DUPLICATE_FOUND: {dup['reason']}", dry_run)
        return {"slug": slug, "status": "DUPLICATE_FOUND", "reason": dup["reason"]}

    # ---------------------------------------------------------- create approval
    approval = {
        "slug":          slug,
        "german_title":  de_title,
        "arabic_title":  ar_title,
        "draft_de":      _relative(de_path),
        "draft_ar":      _relative(ar_path),
        "images":        images,
        "status":        "PENDING",
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }

    pending_path = PENDING_DIR / f"{slug}.json"
    if not dry_run:
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(
            json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    log_action(slug, "create_approval_request", "PENDING", dry_run)
    return {"slug": slug, "status": "PENDING", "path": str(pending_path)}


def main():
    parser = argparse.ArgumentParser(
        description="Create approval requests for draft article pairs"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only — no files created or modified")
    parser.add_argument("--slug", metavar="SLUG",
                        help="Process only this specific slug")
    args = parser.parse_args()

    pairs = find_draft_pairs()
    if not pairs:
        print("No valid draft pairs found.")
        return

    if args.slug:
        pairs = [p for p in pairs if p["slug"] == args.slug]
        if not pairs:
            print(f"Slug '{args.slug}' not found in drafts.")
            sys.exit(1)

    results = []
    for pair in pairs:
        print(f"\nProcessing: {pair['slug']}")
        result = create_approval_request(pair, dry_run=args.dry_run)
        results.append(result)
        status = result["status"]
        if status == "PENDING":
            dest = result.get("path", "(dry-run)")
            print(f"  [OK]   PENDING -> {dest}")
        elif status == "NEEDS_IMAGES":
            print(f"  [SKIP] NEEDS_IMAGES  {result.get('missing_images')}")
        elif status == "DUPLICATE_FOUND":
            print(f"  [SKIP] DUPLICATE_FOUND  {result.get('reason')}")

    n_ok  = sum(1 for r in results if r["status"] == "PENDING")
    n_img = sum(1 for r in results if r["status"] == "NEEDS_IMAGES")
    n_dup = sum(1 for r in results if r["status"] == "DUPLICATE_FOUND")
    print(f"\nSummary: {n_ok} pending / {n_img} needs-images / {n_dup} duplicates")
    if args.dry_run:
        print("\n[DRY-RUN] No files were created or modified.")


if __name__ == "__main__":
    main()
