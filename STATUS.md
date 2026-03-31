# Current Status

This file is a short handoff note for resuming work in a new thread or window.

## What is done

- local SQLite brain is working
- blog, Codex, and Chrome bookmarks import are working
- canonical `items` and compatibility `records` are working
- local read API is working
- local write API for `capture` is working
- local mobile capture page at `/capture` is working
- CLI now supports `capture` in search and timeline filters
- local sync no longer deletes manually created local capture items
- a public Cloudflare Workers capture service has been scaffolded and deployed
- Cloudflare D1 database for cloud capture has been created and initialized
- cloud capture now syncs into local SQLite through `python3 -m personal_brain sync`
- cloud capture now also syncs automatically on local API startup and on a
  background interval
- a dedicated `python3 -m personal_brain sync-cloud-capture` command and
  launchd sync script now exist for operational automation

## Important files

- local API and local capture page:
  [`personal_brain/api.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/api.py)
- local database and capture item creation:
  [`personal_brain/database.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/database.py)
- CLI capture filters:
  [`personal_brain/cli.py`](/Users/taoxuan/Desktop/cloud-brain/personal_brain/cli.py)
- Cloudflare deployment:
  [`cloudflare-capture/src/index.js`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture/src/index.js)
- Cloudflare D1 schema:
  [`cloudflare-capture/schema.sql`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture/schema.sql)
- Cloudflare config:
  [`cloudflare-capture/wrangler.toml`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture/wrangler.toml)

## Current deployed cloud shape

- public capture page is deployed on Cloudflare Workers
- capture writes go into Cloudflare D1
- local brain data still lives in `data/personal_brain.db`
- local SQLite can ingest cloud capture when `python3 -m personal_brain sync` runs
- local API startup now triggers cloud-capture sync and keeps polling for new
  cloud capture rows
- cloud capture is still not merged into local SQLite immediately at write time
- default automatic cadence is now daily rather than near-real-time

## What is not done yet

- no unified query surface that combines local SQLite and cloud D1 capture in
  one read call yet
- no long-term cloud main database yet; current cloud storage is still a
  bridge architecture centered on D1 for capture only

## Best next step

Finish operationalizing the automatic Cloudflare capture sync path into local
SQLite.

Recommended shape:

1. make sure the launchd job is loaded on the Mac
2. preserve stable ids so repeated syncs do not duplicate rows
3. keep source metadata like `device`, `input_type`, and `source_label`
4. optionally add local display conversion from UTC to Berlin time
5. let existing local search, timeline, and show commands keep seeing cloud captures

## Longer-Term Direction

Use the cloud as the main always-on layer.

Recommended long-term shape:

- `capture` becomes cloud-first
- blog, Codex history, and bookmarks remain source-first
- all four sources eventually sync into one cloud canonical database
- local SQLite becomes replica/backup rather than the only main database

Detailed rationale and source-by-source design live in
[`CLOUD_ARCHITECTURE.md`](/Users/taoxuan/Desktop/cloud-brain/CLOUD_ARCHITECTURE.md).

## Recommended Next Prompt

In the next window, start with:

`Read STATUS.md, CLOUD_ARCHITECTURE.md, and ARCHITECTURE.md, then continue making cloud capture sync automatic.`

## Useful local commands

Check local capture items:

```bash
python3 -m personal_brain search "关键词" --kind capture --show-full
python3 -m personal_brain timeline --limit 10 --type capture
python3 -m personal_brain sync
python3 -m personal_brain sync-cloud-capture
```

Check cloud capture rows:

```bash
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
cd /Users/taoxuan/Desktop/cloud-brain/cloudflare-capture
npx wrangler d1 execute cloud-brain-capture --remote --command "SELECT item_id, created_at, title FROM captures ORDER BY created_at DESC LIMIT 10"
```
