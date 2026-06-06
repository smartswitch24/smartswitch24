# SmartSwitch24 Affiliate Agent — Approval & Publishing Automation

Approval-gated publishing pipeline for German + Arabic travel article pairs.

---

## Architecture

```
Claude Code (Windows)          Raspberry Pi (OpenClaw)
──────────────────────         ──────────────────────────────────
Write scripts               →  Git pull every 30 min
Create approval requests    →  Run create_approval_request.py
Generate Telegram previews  →  Send telegram/{slug}.md to Telegram
                            ←  User replies APPROVE:{slug}
                            →  Run process_approval.py
                            →  Run publish_article_pair.py
                                  ↓
                            git push origin main
                                  ↓
                            Cloudflare deploy (auto)
```

All state is managed through JSON files in `approvals/`. Scripts are stateless
and re-runnable. No direct SSH, no Raspberry-path assumptions.

---

## Prerequisites

- Python 3.8+  (standard library only — no `pip install` required)
- `git` in PATH
- Repository cloned and remote `origin` set

---

## Directory Structure

```
automation/affiliate-agent/
├── approvals/
│   ├── pending/          {slug}.json — awaiting decision
│   ├── approved/         {slug}.json — approved, ready to publish
│   └── rejected/         {slug}.json — rejected, will not publish
│
├── logs/
│   └── publishing.log    append-only audit log
│
├── reports/
│   ├── missing-images-{slug}.md   created when images are absent
│   └── duplicate-{slug}.md        created when duplicate detected
│
├── telegram/
│   └── {slug}.md         preview message body for Telegram
│
├── data/                 reserved for future structured data
│
└── scripts/
    ├── utils.py                    shared helpers (paths, parsers, checks)
    ├── create_approval_request.py  Step 1 — validate drafts, create pending JSON
    ├── create_telegram_preview.py  Step 2 — generate Telegram message files
    ├── process_approval.py         Step 3 — move pending → approved/rejected
    └── publish_article_pair.py     Step 4 — publish pair, commit, push
```

---

## Workflow

```
Step 1  create_approval_request.py
        ↓ scans content/drafts/travel/de & ar
        ↓ finds matching slug pairs
        ↓ verifies images exist in public/Images/
        ↓ checks for duplicates in src/content/blog/
        ↓ creates approvals/pending/{slug}.json

Step 2  create_telegram_preview.py
        ↓ reads all pending/*.json
        ↓ creates telegram/{slug}.md preview files
        ↓ (OpenClaw reads these and sends to Telegram)

Step 3  process_approval.py APPROVE:{slug}
        ↓ moves approvals/pending/{slug}.json
        ↓              → approvals/approved/{slug}.json

Step 4  publish_article_pair.py
        ↓ reads all approved/*.json with status APPROVED
        ↓ re-validates all checks
        ↓ copies drafts to src/content/blog/ with draft: false
        ↓ git add / commit / push
        ↓ Cloudflare deploys automatically on push
```

---

## Approval Process

**Pending approval JSON** (`approvals/pending/{slug}.json`):
```json
{
  "slug": "griechenland-pauschalreisen-2026",
  "german_title": "Griechenland Pauschalreisen 2026 ...",
  "arabic_title": "عروض رحلات اليونان الشاملة 2026",
  "draft_de": "content/drafts/travel/de/griechenland-pauschalreisen-2026.md",
  "draft_ar": "content/drafts/travel/ar/griechenland-pauschalreisen-2026.md",
  "images": ["/Images/Travel/05-santorini-greece.webp"],
  "status": "PENDING",
  "created_at": "2026-06-06T12:00:00Z"
}
```

**Status transitions:**
```
PENDING  →  APPROVED   (process_approval.py APPROVE:{slug})
PENDING  →  REJECTED   (process_approval.py REJECT:{slug})
APPROVED →  PUBLISHED  (publish_article_pair.py — automatic on success)
```

---

## Duplicate Protection

Two-layer check in `check_duplicate()`:

| Layer | What is checked | How |
|-------|----------------|-----|
| Slug  | Same filename already in `src/content/blog/de/` or `ar/` | Exact match |
| Title | Similar German title in any published article | Word-overlap ≥ 60 % of significant words |

Title comparison:
- Lowercased and stripped of punctuation
- Stop words removed (German + English)
- Year tokens (2024–2027) ignored
- Threshold: 60 % of the shorter title's significant words must overlap

If a duplicate is detected a report is written to `reports/duplicate-{slug}.md`
and the approval request is **not** created.

---

## Image Validation

`create_approval_request.py` extracts `heroImage` (and `image`, `thumbnail`,
`coverImage`) from both DE and AR frontmatter.

Each reference such as `/Images/Travel/05-santorini-greece.webp` is resolved to:
```
public/Images/Travel/05-santorini-greece.webp
```
If any file is missing, a report is written to `reports/missing-images-{slug}.md`
and status is set to `NEEDS_IMAGES`. The approval request is **not** created.

---

## Publish Process

`publish_article_pair.py` runs these checks before writing any file:

1. Approval JSON status is `APPROVED`
2. `git status --porcelain` is empty (clean working tree)
3. Local `HEAD` matches `origin` (synchronized)
4. German draft file exists on disk
5. Arabic draft file exists on disk
6. All images referenced in approval JSON exist
7. No duplicate slug or similar title in published blog

If all checks pass, for each approved article:
1. Read draft content
2. Replace `draft: true` → `draft: false` in frontmatter (originals unchanged)
3. Write to `src/content/blog/de/{slug}.md`
4. Write to `src/content/blog/ar/{slug}.md`
5. `git add` both files
6. `git commit -m "publish travel article pair: {slug}"`
7. `git push origin main`
8. Mark approval JSON as `PUBLISHED`

---

## Rollback Procedure

If a published article needs to be reverted:

```bash
# 1. Find the commit
git log --oneline | grep "publish travel article pair: {slug}"

# 2. Revert
git revert {commit-hash}
git push origin main

# 3. Reset approval status manually
#    Edit approvals/approved/{slug}.json
#    Change status from "PUBLISHED" back to "APPROVED"
```

The original draft files are never deleted, so re-publishing is possible after
fixing any issue.

---

## Command Reference

All scripts support `--dry-run` (no files modified, no git actions).

```bash
# Create approval requests for all valid draft pairs
python scripts/create_approval_request.py

# Create approval request for a single slug
python scripts/create_approval_request.py --slug griechenland-pauschalreisen-2026

# Generate Telegram preview files for all pending approvals
python scripts/create_telegram_preview.py

# Approve an article
python scripts/process_approval.py APPROVE:griechenland-pauschalreisen-2026

# Reject an article
python scripts/process_approval.py REJECT:griechenland-pauschalreisen-2026

# Publish all approved articles
python scripts/publish_article_pair.py

# Dry-run any command (preview only)
python scripts/create_approval_request.py --dry-run
python scripts/publish_article_pair.py --dry-run
```

---

## Logging

Every action is appended to `logs/publishing.log`:
```
2026-06-06T12:00:00Z | griechenland-pauschalreisen-2026 | create_approval_request | PENDING
2026-06-06T12:01:00Z | griechenland-pauschalreisen-2026 | create_telegram_preview | .../telegram/griechenland-pauschalreisen-2026.md
2026-06-06T12:05:00Z | griechenland-pauschalreisen-2026 | process_approved | .../approved/griechenland-pauschalreisen-2026.json
2026-06-06T12:06:00Z | griechenland-pauschalreisen-2026 | publish | PUBLISHED
```

---

## OpenClaw — Raspberry Pi Integration

`scripts/openclaw_telegram_watcher.py` bridges the publishing pipeline to
Telegram. It runs on the Raspberry Pi after a git pull and does two things:

1. Detects new pending approvals and sends their Telegram preview messages
2. Processes `APPROVE:{slug}` / `REJECT:{slug}` commands from the CLI

No changes to the other four scripts are required.

---

### How the Raspberry Pi runs the watcher

```
[cron every 10 min]
  git pull
  python3 openclaw_telegram_watcher.py --send-pending
      ↓
  Reads  approvals/pending/*.json
  Checks data/telegram_sent.json  (skips already-sent slugs)
  Reads  telegram/{slug}.md
  POSTs  to Telegram Bot API
  Writes data/telegram_sent.json  (marks slug as sent)
  Logs   to logs/telegram-watcher.log

[You reply in Telegram: APPROVE:{slug}]
  Manually run on the Pi:
  python3 openclaw_telegram_watcher.py --process-command APPROVE:{slug}
      ↓
  Calls  process_approval.py APPROVE:{slug}   (pending → approved)
  Calls  publish_article_pair.py --dry-run    (validates, does not publish)
  Prints publish command for manual execution
  Logs   to logs/telegram-watcher.log
```

---

### Environment variables

The watcher reads credentials from environment variables only.
Never hardcode tokens.

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token_here
export TELEGRAM_CHAT_ID=your_chat_id_here
```

**Getting your credentials:**

| Variable | How to get it |
|----------|--------------|
| `TELEGRAM_BOT_TOKEN` | Message @BotFather on Telegram → /newbot → copy the token |
| `TELEGRAM_CHAT_ID` | Message @userinfobot on Telegram → copy the id field |

**Persisting on the Raspberry Pi (choose one):**

Option A — add to `/etc/environment` (system-wide):
```
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

Option B — add to the top of your crontab (`crontab -e`):
```
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

### Testing with --dry-run

`--dry-run` requires no Telegram credentials. Run it on any machine.

```bash
# Preview what would be sent — no messages sent, no state modified
python3 automation/affiliate-agent/scripts/openclaw_telegram_watcher.py \
    --send-pending --dry-run

# Preview what an APPROVE command would do — no files moved, no git actions
python3 automation/affiliate-agent/scripts/openclaw_telegram_watcher.py \
    --process-command APPROVE:griechenland-pauschalreisen-2026 --dry-run
```

---

### Manually processing APPROVE / REJECT

After you receive a Telegram preview and decide to approve or reject:

```bash
# Approve — moves pending → approved, runs publish dry-run, prints publish command
python3 automation/affiliate-agent/scripts/openclaw_telegram_watcher.py \
    --process-command APPROVE:griechenland-pauschalreisen-2026

# Reject — moves pending → rejected
python3 automation/affiliate-agent/scripts/openclaw_telegram_watcher.py \
    --process-command REJECT:griechenland-pauschalreisen-2026
```

---

### Publishing after dry-run passes

Real publishing is **always manual**. The watcher never publishes automatically.

After `--process-command APPROVE:{slug}` runs and the dry-run passes:

```bash
# Publish a single approved article pair
python3 automation/affiliate-agent/scripts/publish_article_pair.py \
    --slug griechenland-pauschalreisen-2026

# Publish all approved articles
python3 automation/affiliate-agent/scripts/publish_article_pair.py
```

This copies drafts to `src/content/blog/`, sets `draft: false`, commits, and
pushes. Cloudflare deploys automatically on push.

---

### State file

`data/telegram_sent.json` tracks which slugs have already been sent.
The watcher creates this file automatically on first run.

```json
{
  "griechenland-pauschalreisen-2026": {
    "sent_at": "2026-06-06T10:00:00+00:00",
    "telegram_message_sent": true
  }
}
```

To re-send a preview (e.g. after editing the telegram file), remove the
slug entry from `telegram_sent.json` and run `--send-pending` again.

---

### Cron setup

See `cron/openclaw-telegram-watcher-example.txt` for a ready-to-copy crontab
line. **Do not enable until the full flow has been tested end-to-end.**

---

### Watcher log

All watcher actions are appended to `logs/telegram-watcher.log`:

```
2026-06-06T10:00:00Z | griechenland-pauschalreisen-2026 | send_telegram | SENT
2026-06-06T10:05:00Z | griechenland-pauschalreisen-2026 | process_approve | OK
2026-06-06T10:05:01Z | griechenland-pauschalreisen-2026 | dry_run_publish | PASSED
```
