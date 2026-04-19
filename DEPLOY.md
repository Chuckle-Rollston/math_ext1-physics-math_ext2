# Deploying to Vercel

## 1. Provision a Postgres database

Any of these work (free tiers):

- **Neon** (https://neon.tech) — easy, generous free tier.
- **Supabase** (https://supabase.com) — includes auth/storage if you want it later.
- **Vercel Postgres** — linked via the Vercel dashboard, one click.

Copy the connection string. It looks like
`postgresql://user:pass@host/dbname` (Neon adds `?sslmode=require`, which is
fine — leave it in).

## 2. Import the repo into Vercel

1. Go to https://vercel.com/new and import the GitHub repo.
2. Framework preset: **Other**. Leave build/output settings at defaults —
   `vercel.json` configures everything.
3. Add environment variables under **Settings → Environment Variables**:
   - `DATABASE_URL` — the Postgres URL from step 1. Set for Production and
     Preview at minimum.
   - `SECRET_KEY` — any long random string (e.g. `python -c "import secrets;
     print(secrets.token_hex(32))"`). **Required** — without it, the fallback
     regenerates per worker and sessions die on every cold start.
4. Deploy.

## 3. First-run table creation

`app.py` calls `db.create_all()` on import, so the first request after
deploy creates all tables automatically. The lightweight `ALTER TABLE`
migration at the bottom of `app.py` also runs — it's a no-op for a fresh DB.

## Local development

Local dev still uses SQLite:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

To test against Postgres locally, export `DATABASE_URL` before running.

## Notes and gotchas

- **Static files**: served directly by Vercel from `/static/*` via
  `vercel.json` routes — no Flask involvement in production.
- **MathJax**: loaded from the jsdelivr CDN in `templates/base.html`. No
  bundling needed.
- **Cold starts**: the first request after inactivity spins up a new
  function and re-runs `db.create_all()` (idempotent). Expect ~1–2 s.
- **Free-tier Postgres**: Neon and Supabase suspend idle databases. First
  request after suspension adds a few seconds of latency — harmless for a
  small user base.
- **Don't commit the database**. `app.db` is in `.gitignore`.
