# Cloudflare Capture

This folder contains a cloud-native capture service for Cloudflare Workers.

It is the next step after validating the local prototype:

- phone opens a small mobile capture page
- Typeless AI transcribes speech into the text box
- one tap saves the thought into a cloud-hosted D1 database

## What it does

- serves a mobile capture page at `/capture`
- protects the page and API with a secret token
- stores captures in Cloudflare D1
- lets the page load the latest saved captures

## Important scope

This service stores captures in Cloudflare D1, not in the local SQLite
database inside this repo.

That is intentional for the first cloud version, because it removes the need to
keep your Mac online.

Recommended next step after deployment:

- add a sync path that imports cloud captures back into the local brain database

## Deploy

These steps follow Cloudflare's official Workers and D1 flow:

1. Log in to Cloudflare:

```bash
npx wrangler login
```

2. Create the D1 database:

```bash
cd /Users/taoxuan/Desktop/cloud-brain/cloudflare-capture
npx wrangler d1 create cloud-brain-capture
```

Cloudflare will print a `database_id`. Copy that value into
[`wrangler.toml`](/Users/taoxuan/Desktop/cloud-brain/cloudflare-capture/wrangler.toml)
and replace `REPLACE_WITH_D1_DATABASE_ID`.

3. Create the schema:

```bash
npx wrangler d1 execute cloud-brain-capture --file=./schema.sql
```

4. Set a secret token:

```bash
npx wrangler secret put CAPTURE_TOKEN
```

Use a long random value. The capture page will be opened with
`?token=YOUR_SECRET`.

5. Deploy:

```bash
npx wrangler deploy
```

After deployment, Wrangler will print your public Workers URL.

## Use

Open:

```text
https://your-worker-subdomain.workers.dev/capture?token=YOUR_SECRET
```

The page will:

- let you type or use Typeless AI voice input
- save to `/captures`
- show the latest saved records

## API

- `GET /health`
- `GET /capture?token=...`
- `GET /captures` with token header or query token
- `POST /captures` with token header or query token

## Security

Do not share the full `capture?token=...` URL casually.

If the token leaks:

1. set a new `CAPTURE_TOKEN` with `wrangler secret put`
2. redeploy
3. stop using the old link
