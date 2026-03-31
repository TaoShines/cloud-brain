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
- local SQLite has not yet been merged with cloud capture automatically

## What is not done yet

- no sync from Cloudflare D1 back into local SQLite yet
- no deduplicated importer for cloud capture rows yet
- no unified query surface that combines local SQLite and cloud D1 capture in
  one read call yet

## Best next step

Implement a Cloudflare capture sync path into local SQLite.

Recommended shape:

1. add a new sync command or importer that reads rows from Cloudflare D1
2. map each cloud row into canonical local `MemoryItem`
3. preserve stable ids so repeated syncs do not duplicate rows
4. store source metadata like `device`, `input_type`, and `source_label`
5. let existing local search, timeline, and show commands see cloud captures

## Useful local commands

Check local capture items:

```bash
python3 -m personal_brain search "关键词" --kind capture --show-full
python3 -m personal_brain timeline --limit 10 --type capture
```

Check cloud capture rows:

```bash
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
cd /Users/taoxuan/Desktop/cloud-brain/cloudflare-capture
npx wrangler d1 execute cloud-brain-capture --remote --command "SELECT item_id, created_at, title FROM captures ORDER BY created_at DESC LIMIT 10"
```
