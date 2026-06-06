"""Shared utilities for SmartSwitch24 affiliate agent automation."""
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path layout
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent          # .../scripts
AGENT_DIR   = SCRIPTS_DIR.parent                       # .../affiliate-agent
REPO_ROOT   = AGENT_DIR.parent.parent                  # .../smartswitch24

DRAFTS_DE = REPO_ROOT / "content" / "drafts" / "travel" / "de"
DRAFTS_AR = REPO_ROOT / "content" / "drafts" / "travel" / "ar"
BLOG_DE   = REPO_ROOT / "src" / "content" / "blog" / "de"
BLOG_AR   = REPO_ROOT / "src" / "content" / "blog" / "ar"
IMAGES_DIR = REPO_ROOT / "public" / "Images"

PENDING_DIR  = AGENT_DIR / "approvals" / "pending"
APPROVED_DIR = AGENT_DIR / "approvals" / "approved"
REJECTED_DIR = AGENT_DIR / "approvals" / "rejected"
REPORTS_DIR  = AGENT_DIR / "reports"
TELEGRAM_DIR = AGENT_DIR / "telegram"
LOGS_DIR     = AGENT_DIR / "logs"
LOG_FILE     = LOGS_DIR / "publishing.log"

# ---------------------------------------------------------------------------
# Stop words for title-similarity duplicate detection
# ---------------------------------------------------------------------------
STOP_WORDS = {
    # German
    "der", "die", "das", "und", "oder", "in", "im", "zu", "für",
    "mit", "von", "auf", "an", "am", "ein", "eine", "bei", "aus",
    "nach", "wie", "auch", "mehr", "alle",
    # English / generic
    "a", "the", "and", "or", "in", "for", "to", "of", "at", "on",
    # Years to ignore
    "2024", "2025", "2026", "2027",
}

# Slugs that are meta / non-article files and should never be treated as pairs
_EXCLUDED_SLUG_PREFIXES = ("internal-linking",)

# ---------------------------------------------------------------------------
# Frontmatter parser (no external dependencies)
# ---------------------------------------------------------------------------

def parse_frontmatter(file_path: Path) -> dict:
    """Parse simple key: value YAML frontmatter from a markdown file."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm: dict = {}
    for line in match.group(1).splitlines():
        # Match: key: "optional-quoted value" or key: unquoted value
        kv = re.match(r'^([\w][\w\-]*):\s*"?([^"#\n]*?)"?\s*$', line)
        if kv:
            fm[kv.group(1)] = kv.group(2).strip()
    return fm


def set_draft_false(content: str) -> str:
    """Replace 'draft: true' with 'draft: false' inside frontmatter only."""
    match = re.match(r"^(---\s*\n)(.*?)\n(---)", content, re.DOTALL)
    if not match:
        return content
    fm_body = re.sub(
        r"^(draft:\s*)true\s*$", r"\1false",
        match.group(2),
        flags=re.MULTILINE,
    )
    return match.group(1) + fm_body + "\n" + match.group(3) + content[match.end():]

# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def get_frontmatter_images(fm: dict) -> list:
    """Return image paths referenced in frontmatter (deduplicated, non-empty)."""
    images = []
    for key in ("heroImage", "image", "thumbnail", "coverImage"):
        val = fm.get(key, "").strip()
        if val and val not in images:
            images.append(val)
    return images


def image_exists(image_ref: str) -> bool:
    """Check whether an image reference such as /Images/Travel/foo.webp resolves."""
    rel = image_ref.lstrip("/")
    return (REPO_ROOT / "public" / rel).exists()

# ---------------------------------------------------------------------------
# Draft pair discovery
# ---------------------------------------------------------------------------

def find_draft_pairs() -> list:
    """Return list of dicts for every valid German+Arabic draft pair."""
    pairs = []
    if not DRAFTS_DE.exists() or not DRAFTS_AR.exists():
        return pairs

    de_map = {
        f.stem: f for f in DRAFTS_DE.glob("*.md")
        if not any(f.stem.startswith(p) for p in _EXCLUDED_SLUG_PREFIXES)
    }
    ar_map = {
        f.stem: f for f in DRAFTS_AR.glob("*.md")
        if not any(f.stem.startswith(p) for p in _EXCLUDED_SLUG_PREFIXES)
    }

    for slug in sorted(de_map):
        if slug in ar_map:
            pairs.append({
                "slug":    slug,
                "de_path": de_map[slug],
                "ar_path": ar_map[slug],
            })
    return pairs

# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> set:
    """Return the set of significant words from a title (for similarity check)."""
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    return {w for w in cleaned.split() if w not in STOP_WORDS and len(w) > 2}


def _titles_similar(t1: str, t2: str, threshold: float = 0.75) -> bool:
    """True if t1 and t2 share >= threshold fraction of significant words."""
    w1, w2 = _normalize_title(t1), _normalize_title(t2)
    if not w1 or not w2:
        return False
    overlap = w1 & w2
    return len(overlap) / min(len(w1), len(w2)) >= threshold


def check_duplicate(slug: str, de_title: str, ar_title: str) -> dict:
    """
    Return {"is_duplicate": bool, "reason": str}.

    Checks:
      1. Same slug already in blog/de or blog/ar
      2. German title similar to any existing published title
    """
    # 1. Slug check (fastest)
    for target in (BLOG_DE / f"{slug}.md", BLOG_AR / f"{slug}.md"):
        if target.exists():
            return {
                "is_duplicate": True,
                "reason": f"Slug '{slug}' is already published ({target.relative_to(REPO_ROOT).as_posix()})",
            }

    # 2. Title-similarity check across published blog
    for blog_dir in (BLOG_DE, BLOG_AR):
        if not blog_dir.exists():
            continue
        for md in blog_dir.glob("*.md"):
            fm = parse_frontmatter(md)
            existing = fm.get("title", "")
            if existing and _titles_similar(de_title, existing):
                return {
                    "is_duplicate": True,
                    "reason": (
                        f"Title similar to existing article '{existing}' "
                        f"({md.relative_to(REPO_ROOT).as_posix()})"
                    ),
                }

    return {"is_duplicate": False, "reason": ""}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_action(slug: str, action: str, result: str, dry_run: bool = False) -> None:
    """Append one line to automation/affiliate-agent/logs/publishing.log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = "[DRY-RUN] " if dry_run else ""
    line = f"{ts} | {slug} | {action} | {prefix}{result}\n"
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line)
    logging.info(line.rstrip())
