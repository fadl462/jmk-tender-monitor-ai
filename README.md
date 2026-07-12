# JMK Tender Monitor AI

A single deployable application — dashboard, opportunity intelligence,
pipeline tracking, an AI Assistant, and a daily Ghana-first crawler — built
as one FastAPI service rather than separate frontend/backend/crawler
deployments. Same user-facing ambition, one thing to deploy instead of
three, using a **real Postgres database** (via Supabase's free tier) so
data survives restarts properly — no more ephemeral-disk surprises.

## Important: "AI" here means free rule-based logic, not a paid model

There is **no Anthropic/OpenAI API call anywhere** in this app:
- **Opportunity scoring** — keyword matching against JMK's sectors and
  research/consultancy language (see `app/crawler.py`).
- **The AI Assistant** — a rule-based natural-language-ish query parser
  (see `app/routes/assistant.py`). It recognizes sector names, org names,
  "tender"/"job", and phrases like "this week" in your question, and
  filters accordingly. It's honest about this in its own responses.

This keeps the whole thing free to run forever. The trade-off: it's less
flexible than a real LLM would be with oddly-phrased questions or unusual
listing text — treat it as smart filtering, not a conversational AI.

## Local development

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit `http://localhost:8000`. Without `DATABASE_URL` set, it uses a local
SQLite file (`local_dev.db`) automatically — good for trying things out
before connecting a real database.

## Step 1 — Create a free Supabase database

1. Go to [supabase.com](https://supabase.com) → sign up (no card needed).
2. **New Project** → give it a name, set a database password (save it
   somewhere), pick a region close to Ghana (e.g. Europe West).
3. Once created, go to **Project Settings → Database → Connection string**.
4. Copy the **URI** format connection string — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxx.supabase.co:5432/postgres
   ```
5. Replace `[YOUR-PASSWORD]` with the database password from step 2. This
   full string is your `DATABASE_URL`.

The app creates its own tables automatically on first start — no manual
schema setup needed.

## Step 2 — Push to GitHub

Push the contents of this `backend/` folder to a GitHub repository (public
or private — Render can access private repos).

## Step 3 — Deploy on Render

1. Go to [render.com](https://render.com), sign up with GitHub.
2. **New +** → **Blueprint** → select your repo. Render reads `render.yaml`
   and sets up the build/start commands automatically.
3. Under the service's **Environment** tab, fill in the values `render.yaml`
   left blank:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your Supabase connection string from Step 1 |
   | `SMTP_HOST` | `smtp.gmail.com` |
   | `SMTP_PORT` | `587` |
   | `SMTP_USER` | your sending Gmail address |
   | `SMTP_PASSWORD` | a Gmail **app password** (myaccount.google.com/apppasswords — requires 2-Step Verification turned on first) |
   | `DIGEST_FROM` | same as `SMTP_USER` |
   | `DIGEST_RECIPIENTS` | comma-separated recipient emails |
   | `CRON_SECRET` | any random string you make up |

4. Save — Render redeploys automatically with these values.
5. Visit the URL Render gives you (e.g. `jmk-tender-monitor-ai.onrender.com`)
   — you should see the dashboard.

## Step 4 — Set up the daily automatic crawl

Render's free tier spins down after ~15 minutes of no traffic, so an
in-process schedule can't be trusted to fire at exactly 7am. The fix is the
same one that worked before: an external free scheduler pings the crawl
endpoint, which wakes the app and runs the check.

1. Go to [cron-job.org](https://cron-job.org) (free, no card).
2. Create a job:
   - **URL:** `https://<your-app>.onrender.com/api/crawl/run?token=<your CRON_SECRET>`
   - **Method:** POST
   - **Schedule:** daily at `07:00`, timezone **Africa/Accra**
3. Save. From then on, every morning it triggers the crawl automatically.

You can also trigger it manually any time from the **Settings** page in the
app itself ("Run Crawl Now").

## Pointing a JMK subdomain at it

Same as before — Render supports custom domains free:
1. Service **Settings → Custom Domains → Add Custom Domain** →
   `tenders.jmkconsultinggroup.com`.
2. Add the CNAME record Render gives you to JMK's DNS settings.
3. Render auto-provisions free SSL once verified.

## Project layout

```
backend/
  app/
    main.py            FastAPI app, mounts routes + serves the frontend
    database.py         SQLAlchemy engine/session (Postgres or SQLite fallback)
    models.py            Opportunity, BoardItem, CrawlStatus tables
    schemas.py            Pydantic request/response models
    crawler.py             Free rule-based crawling, scoring, email digest
    config.py               Environment variable settings
    routes/
      opportunities.py       GET /api/opportunities, /api/opportunities/stats
      board.py                 Pipeline CRUD + "track this opportunity"
      crawl.py                   Trigger + status polling
      assistant.py                 Rule-based natural-language filtering
    templates/index.html          Dashboard page
    static/
      style.css                    JMK-branded styling, light + dark mode
      app.js                         Frontend logic
      jmk-logo.png                    Logo
render.yaml                Render Blueprint definition
Procfile                    Start command
requirements.txt
```

## Adjusting sensitivity

- `MIN_MATCH_SCORE` (default 40) — raise to see only stronger matches.
- `MIN_GHANA_JOB_RESULTS` (default 5) — how many qualifying Ghana job
  matches count as "enough" before international sources get checked.
- `FEED_WINDOW_DAYS` (default 30) — how long an item without a deadline
  stays in the feed before aging out.

## What's intentionally not included (yet)

Matching the spec's own "Future AI" section: proposal drafting, bid/no-bid
recommendations, TOR summarization, WhatsApp/Teams alerts, and a native
mobile app aren't built here. Login/authentication is also left out for
now, on the assumption this is an internal tool for a small team rather
than something needing access control — worth revisiting if that changes.
