# Cloud Brain Cloud Architecture

## Goal

Move Cloud Brain toward a long-lived cloud-backed architecture that does not
depend on the local Mac staying online.

The desired end state is:

- capture works from anywhere on the public internet
- the main memory database lives in the cloud
- sync jobs do not depend on the local Mac being awake at 02:00
- original source data remains traceable and recoverable

## Core Principle

Do not treat the cloud database as a replacement for every original source
file.

Instead:

- keep original source data in its native home when that makes sense
- sync each source into one cloud canonical memory database
- preserve source traceability, stable ids, and checksums
- optionally keep a local SQLite replica for offline analysis, backup, or
  experimentation

This keeps the system trustworthy and reversible.

## Data Strategy By Source

### 1. Capture

Capture should be cloud-first.

Why:

- it is created on the phone
- it needs to work from anywhere
- it should not depend on the local Mac

Recommended source-of-truth:

- cloud database

Recommended flow:

1. phone opens the public capture page
2. Typeless AI turns speech into text
3. Cloudflare Worker receives the request
4. cloud database stores the capture immediately
5. local replica sync is optional and secondary

### 2. Blog

Blog should remain source-first in the blog repository.

Why:

- the blog repo is the real authoring source
- Markdown files remain the easiest canonical editorial format
- the cloud database should be a memory projection, not the only copy

Recommended source-of-truth:

- blog repository Markdown

Recommended flow:

1. importer reads Markdown and frontmatter
2. importer maps entries into canonical memory items
3. cloud database stores the projected items
4. metadata keeps `slug`, `source_path`, `checksum`, and timestamps

### 3. Codex Conversations And Messages

Codex history should remain source-first in Codex state and rollout files.

Why:

- rollout files are the original detailed conversation record
- the cloud brain should store normalized memory items, not replace the raw
  history

Recommended source-of-truth:

- Codex thread state database and rollout JSONL files

Recommended flow:

1. importer reads thread metadata and rollout messages
2. importer maps them into `conversation` and `message` items
3. cloud database stores those items with stable ids
4. metadata keeps `thread_id`, `message_index`, `cwd`, `model`, and source info

### 4. Chrome Bookmarks

Bookmarks should remain source-first in Chrome bookmark data.

Why:

- Chrome is still the native system of record
- the cloud brain is better used as an interest and attention history layer

Recommended source-of-truth:

- Chrome bookmark export / bookmark file

Recommended flow:

1. importer reads Chrome bookmark metadata
2. importer maps bookmarks into canonical bookmark items
3. cloud database stores `url`, `folder_path`, `added_at`, `status`,
   `deleted_at`, and related metadata
4. lifecycle changes remain trackable across syncs

## Recommended Long-Term Architecture

The system should evolve into three layers.

### 1. Source Layer

This is where original source data continues to live.

Examples:

- blog Markdown repository
- Codex thread database and rollout files
- Chrome bookmarks file
- phone capture submission events

### 2. Cloud Brain Layer

This becomes the main shared memory system.

Recommended database:

- Postgres for the long-term main cloud brain

Why Postgres:

- better fit for a growing multi-source system
- stronger long-term support for indexing, relationships, and scheduled jobs
- easier future evolution than treating D1 as the only permanent brain store

Recommended entities:

- `sources`
- `items`
- `item_tags`
- later: `sync_runs`
- later: `item_versions`
- later: `item_links`

### 3. Local Replica Layer

Local SQLite remains useful, but no longer has to be the only main database.

Recommended role:

- local replica
- local backup
- offline querying
- development and experimentation

## Near-Term Transitional Architecture

The current system is already partly in this transition:

- public capture runs on Cloudflare Workers
- cloud capture currently lands in Cloudflare D1
- local SQLite still stores the main local brain
- local sync can now pull cloud capture rows back into local SQLite

This is a valid bridge architecture, but not yet the final target.

## Recommended Evolution Path

### Phase A: Public Input Stabilization

Status:

- done enough to validate the workflow

Includes:

- public capture page
- token protection
- cloud capture storage
- local sync back into SQLite

### Phase B: Cloud Canonical Database

Goal:

introduce a long-term cloud main database for all canonical items.

Recommended move:

- choose Postgres as the cloud main database

Then:

- keep Cloudflare Workers as the public input entry
- write capture into the cloud main database
- stop treating local SQLite as the only main brain

### Phase C: Source Importers To Cloud

Goal:

sync all existing sources into the cloud main database.

Suggested order:

1. bookmarks
2. blog
3. Codex history

Why this order:

- bookmarks are simplest and lowest risk
- blog is structured and stable
- Codex history is richest and most complex

### Phase D: Automated Cloud Sync

Goal:

remove dependence on the Mac for recurring sync.

Recommended behavior:

- scheduled cloud-side jobs import supported sources when possible
- sources that still require local access can sync through a local helper until
  they are redesigned
- the main brain remains online even when the Mac is offline

## Stable ID Strategy

Every source synced into the cloud main database must preserve stable ids.

Recommended examples:

- capture: cloud-generated stable id
- blog: relative path or slug-based id
- Codex conversation: `thread_id`
- Codex message: `thread_id:message_index`
- bookmark: Chrome bookmark guid or stable bookmark id

This is necessary for:

- deduplication
- repeatable sync
- update detection
- deletion tracking
- trustworthy cross-system references

## Time Strategy

Use UTC in storage.

Why:

- easiest for sync
- easiest for cross-device consistency
- avoids daylight-saving confusion in stored data

Recommended display behavior:

- convert to user-local time in UI
- for the current user, default display can be Europe/Berlin

This means:

- storage stays stable and comparable
- viewing feels local and human-friendly

## Cost Strategy

Recommended mindset:

- keep the public capture edge lightweight
- keep the long-term brain on a cloud database that can grow with the project
- avoid forcing the Mac to act as infrastructure

Practical recommendation:

- Cloudflare Workers for the public capture entry
- Postgres for the long-term cloud main brain
- local SQLite as replica/backup, not as the only always-on dependency

## What Should Happen Next

The next design and implementation step should be:

1. define the long-term cloud canonical schema
2. choose the cloud main database
3. decide how local SQLite relates to the cloud database
4. migrate capture from "cloud sidecar" into the chosen cloud main brain
5. import bookmarks into the cloud main brain
6. then import blog
7. then import Codex history

## Summary

Long-term, the system should work like this:

- capture is cloud-first
- blog, Codex, and bookmarks remain source-first
- all four sources sync into one cloud canonical brain
- local SQLite becomes a replica and backup layer
- time is stored in UTC and displayed in local time
- recurring operation should not depend on the Mac staying awake
