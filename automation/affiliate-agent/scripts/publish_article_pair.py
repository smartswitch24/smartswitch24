"""
Publish approved article pairs to the live blog directories.

Publishing checklist (all must pass before any file is written):
  1. Approval JSON exists in approved/ with status APPROVED
  2. Git working tree has no modified tracked files
     (untracked files such as automation/affiliate-agent/ are tolerated)
  3. Local branch is synchronized with remote
  4. German draft file exists
  5. Arabic draft file exists
  6. All referenced images exist in public/Images/
  7. No duplicate slug or similar title already published

On success the LIVE copy is normalized automatically — the draft is NOT touched:
  • draft: true       →  draft: false
  • slug:             →  de/{slug}  /  ar/{slug}
  • category:         →  reisen  (lowercase, unquoted)
  • pubDate:          →  today's date in YYYY-MM-DD (UTC, at publish time)

File moves:
  content/drafts/travel/de/{slug}.md  →  src/content/blog/de/{slug}.md
  content/drafts/travel/ar/{slug}.md  →  src/content/blog/ar/{slug}.md

Draft archival (same commit):
  content/drafts/travel/de/{slug}.md  →  content/drafts/travel/published/de/{slug}.md
  content/drafts/travel/ar/{slug}.md  →  content/drafts/travel/published/ar/{slug}.md

git add / git commit / git push  (skipped in --dry-run)
Approval JSON status updated to PUBLISHED.

Usage:
    python publish_article_pair.py [--dry-run] [--slug SLUG]
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    REPO_ROOT, APPROVED_DIR, PENDING_DIR, BLOG_DE, BLOG_AR, DRAFTS_DE, DRAFTS_AR,
    DRAFTS_PUBLISHED_DE, DRAFTS_PUBLISHED_AR,
    parse_frontmatter, get_frontmatter_images,
    image_exists, check_duplicate, set_draft_false, log_action,
)

# ---------------------------------------------------------------------------
# Frontmatter normalization helpers
# ---------------------------------------------------------------------------

def _in_frontmatter(content: str, transform) -> str:
    """Apply transform() to the frontmatter body and reassemble the file."""
    m = re.match(r'^(---\s*\n)(.*?)\n(---)', content, re.DOTALL)
    if not m:
        return content
    return m.group(1) + transform(m.group(2)) + '\n' + m.group(3) + content[m.end():]


def _set_field(content: str, field: str, value: str) -> str:
    """Replace field: <anything> (quoted or unquoted) with field: value."""
    def transform(fm):
        return re.sub(
            rf'^{re.escape(field)}:\s*"?[^\n"]+"?\s*$',
            f'{field}: {value}',
            fm,
            flags=re.MULTILINE,
        )
    return _in_frontmatter(content, transform)


def _normalize_category(content: str) -> str:
    """Lowercase category value and strip surrounding quotes."""
    def transform(fm):
        return re.sub(
            r'^(category:\s*)"?(\w+)"?\s*$',
            lambda m: f'category: {m.group(2).lower()}',
            fm,
            flags=re.MULTILINE,
        )
    return _in_frontmatter(content, transform)


def _prepare_content(content: str, slug_with_prefix: str, pub_date: str) -> str:
    """
    Apply all publish-time frontmatter normalizations.

    Order matters — set_draft_false runs first on the raw content.
    """
    content = set_draft_false(content)
    content = _set_field(content, "slug", slug_with_prefix)
    content = _normalize_category(content)
    content = _set_field(content, "pubDate", pub_date)
    return content


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(*args, check=True):
    return subprocess.run(
        ["git", *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
        check=check,
    )


def check_git_state(allowed_paths: set = None) -> dict:
    """
    Verify no tracked files are modified/staged and branch is in sync.

    allowed_paths: POSIX paths relative to REPO_ROOT that are permitted to
        appear dirty. Used to allow the expected pending→approved JSON move
        for the slug being published without blocking the publish.

    Untracked files (status lines starting with '??') are always tolerated.
    """
    allowed = allowed_paths or set()
    try:
        status = _run_git("status", "--porcelain", check=False)
        if status.returncode != 0:
            return {"ok": False, "error": "git status failed"}

        dirty_tracked = []
        for line in status.stdout.splitlines():
            if not line:
                continue
            if line.startswith("??"):
                continue
            # git status --porcelain: "XY path" — path starts at column 3
            path_part = line[3:].strip()
            if path_part in allowed:
                continue
            dirty_tracked.append(line)

        if dirty_tracked:
            return {
                "ok": False,
                "error": (
                    "Git working tree has modified tracked files:\n"
                    + "\n".join(dirty_tracked)
                ),
            }

        _run_git("fetch", "--quiet", check=False)

        local  = _run_git("rev-parse", "HEAD",  check=False).stdout.strip()
        remote = _run_git("rev-parse", "@{u}",  check=False).stdout.strip()

        if remote and local != remote:
            return {
                "ok": False,
                "error": "Local branch is not synchronized with remote. Run 'git pull' first.",
            }

        return {"ok": True}
    except FileNotFoundError:
        return {"ok": False, "error": "git is not available in PATH"}


# ---------------------------------------------------------------------------
# Publishing logic
# ---------------------------------------------------------------------------

def publish_pair(approval: dict, dry_run: bool = False) -> dict:
    slug    = approval["slug"]
    de_src  = DRAFTS_DE / f"{slug}.md"
    ar_src  = DRAFTS_AR / f"{slug}.md"
    de_dest = BLOG_DE   / f"{slug}.md"
    ar_dest = BLOG_AR   / f"{slug}.md"
    images  = [i for i in approval.get("images", []) if i]

    # POSIX paths for this slug's approval JSONs (relative to REPO_ROOT).
    # These are whitelisted in the git dirty-state check so that a
    # pending→approved move done by process_approval.py does not block publishing.
    approved_json_path = (APPROVED_DIR / f"{slug}.json").relative_to(REPO_ROOT).as_posix()
    pending_json_path  = (PENDING_DIR  / f"{slug}.json").relative_to(REPO_ROOT).as_posix()
    allowed_git_paths  = {approved_json_path, pending_json_path}

    # ── Git state check (per-slug, knows the allowed approval JSON paths) ────
    if not dry_run:
        state = check_git_state(allowed_paths=allowed_git_paths)
        if not state["ok"]:
            return {"success": False, "slug": slug,
                    "error": f"Git state error: {state['error']}"}

    # ── Pre-flight checks ────────────────────────────────────────────────────
    if not de_src.exists():
        return {"success": False, "slug": slug,
                "error": f"German draft not found: {de_src.relative_to(REPO_ROOT).as_posix()}"}
    if not ar_src.exists():
        return {"success": False, "slug": slug,
                "error": f"Arabic draft not found: {ar_src.relative_to(REPO_ROOT).as_posix()}"}

    missing = [img for img in images if not image_exists(img)]
    if missing:
        return {"success": False, "slug": slug,
                "error": f"Missing images: {missing}"}

    de_fm = parse_frontmatter(de_src)
    ar_fm = parse_frontmatter(ar_src)
    dup   = check_duplicate(slug, de_fm.get("title", slug), ar_fm.get("title", slug))
    if dup["is_duplicate"]:
        return {"success": False, "slug": slug,
                "error": f"Duplicate detected: {dup['reason']}"}

    if dry_run:
        log_action(slug, "publish", "DRY-RUN: pre-flight passed", dry_run=True)
        return {
            "success": True,
            "slug":    slug,
            "dry_run": True,
            "de_src":  de_src.relative_to(REPO_ROOT).as_posix(),
            "ar_src":  ar_src.relative_to(REPO_ROOT).as_posix(),
            "de_dest": de_dest.relative_to(REPO_ROOT).as_posix(),
            "ar_dest": ar_dest.relative_to(REPO_ROOT).as_posix(),
        }

    # ── Normalize and write live files ───────────────────────────────────────
    pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    BLOG_DE.mkdir(parents=True, exist_ok=True)
    BLOG_AR.mkdir(parents=True, exist_ok=True)
    de_dest.write_text(
        _prepare_content(de_src.read_text(encoding="utf-8"), f"de/{slug}", pub_date),
        encoding="utf-8",
    )
    ar_dest.write_text(
        _prepare_content(ar_src.read_text(encoding="utf-8"), f"ar/{slug}", pub_date),
        encoding="utf-8",
    )

    # ── Mark approval PUBLISHED (written before commit so it lands in the same commit) ──
    approval["status"]       = "PUBLISHED"
    approval["published_at"] = datetime.now(timezone.utc).isoformat()
    (APPROVED_DIR / f"{slug}.json").write_text(
        json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Archive drafts + Git commit + push ───────────────────────────────────
    archived_de = DRAFTS_PUBLISHED_DE / f"{slug}.md"
    archived_ar = DRAFTS_PUBLISHED_AR / f"{slug}.md"
    try:
        DRAFTS_PUBLISHED_DE.mkdir(parents=True, exist_ok=True)
        DRAFTS_PUBLISHED_AR.mkdir(parents=True, exist_ok=True)
        _run_git("mv",
                 str(de_src.relative_to(REPO_ROOT)),
                 str(archived_de.relative_to(REPO_ROOT)))
        _run_git("mv",
                 str(ar_src.relative_to(REPO_ROOT)),
                 str(archived_ar.relative_to(REPO_ROOT)))
        _run_git("add",
                 str(de_dest.relative_to(REPO_ROOT)),
                 str(ar_dest.relative_to(REPO_ROOT)))
        # Include approval JSON in commit (check=False: may be untracked)
        _run_git("add", approved_json_path, check=False)
        _run_git("rm", "--cached", "--quiet", pending_json_path, check=False)
        _run_git("commit", "-m", f"publish travel article pair: {slug}")
        _run_git("push", "origin", "main")
    except subprocess.CalledProcessError as exc:
        log_action(slug, "publish", f"GIT_ERROR: {exc.stderr.strip()}")
        return {"success": False, "slug": slug,
                "error": f"Git operation failed: {exc.stderr.strip()}"}

    log_action(slug, "publish", "PUBLISHED")
    return {
        "success":     True,
        "slug":        slug,
        "de_dest":     de_dest.relative_to(REPO_ROOT).as_posix(),
        "ar_dest":     ar_dest.relative_to(REPO_ROOT).as_posix(),
        "de_archived": archived_de.relative_to(REPO_ROOT).as_posix(),
        "ar_archived": archived_ar.relative_to(REPO_ROOT).as_posix(),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Publish approved article pairs to the live blog"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only — no files written, no git operations")
    parser.add_argument("--slug", metavar="SLUG",
                        help="Publish only this specific slug")
    args = parser.parse_args()

    if not APPROVED_DIR.exists():
        print("No approved approvals directory found.")
        return

    approved_files = sorted(APPROVED_DIR.glob("*.json"))
    approved_files = [
        f for f in approved_files
        if json.loads(f.read_text(encoding="utf-8")).get("status") == "APPROVED"
    ]

    if not approved_files:
        print("No articles with status APPROVED.")
        return

    if args.slug:
        approved_files = [f for f in approved_files if f.stem == args.slug]
        if not approved_files:
            print(f"No approved article for slug '{args.slug}'.")
            sys.exit(1)

    results = []
    for json_file in approved_files:
        approval = json.loads(json_file.read_text(encoding="utf-8"))
        slug     = approval["slug"]
        print(f"\nPublishing: {slug}")
        result   = publish_pair(approval, dry_run=args.dry_run)
        results.append(result)

        if result["success"]:
            if args.dry_run:
                print(f"  [DRY-RUN] Would copy:")
                print(f"    {result['de_src']}  ->  {result['de_dest']}")
                print(f"    {result['ar_src']}  ->  {result['ar_dest']}")
                print(f"  [DRY-RUN] Normalizations applied at write time:")
                print(f"    draft: false | slug prefixed | category: reisen | pubDate: <today>")
                print(f"  [DRY-RUN] git commit + push skipped")
            else:
                print(f"  [OK] {result['de_dest']}")
                print(f"  [OK] {result['ar_dest']}")
                print(f"  [OK] draft archived → {result['de_archived']}")
                print(f"  [OK] draft archived → {result['ar_archived']}")
                print(f"  [OK] git push done")
        else:
            print(f"  [FAIL] {result['error']}")

    published = sum(1 for r in results if r["success"] and not r.get("dry_run"))
    failed    = sum(1 for r in results if not r["success"])
    print(f"\nSummary: {len(results)} processed / {published} published / {failed} failed")
    if args.dry_run:
        print("[DRY-RUN] No files written, no git operations performed.")


if __name__ == "__main__":
    main()
