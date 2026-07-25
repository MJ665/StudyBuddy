# StudyBuddy — Deployment Guide

Plain-English, step-by-step. Follow Part A → B → C → D in order.

---

## 0. What are we deploying? (the mental model)

You have **two apps** in one repository (a "monorepo"):

| App | Folder | Runs on | Becomes |
|-----|--------|---------|---------|
| **Frontend** (the website people see) | `apps/web-next` | **Vercel** | `https://studybuddy.mj665.in` |
| **Backend** (the API + database brain) | `apps/api` | **Railway** | `https://studybuddy-api.mj665.in` |

Plus a **mobile app** (`apps/mobile`) that is just a wrapper showing the website — you deploy it *after* the website is live (separate guide, not needed to go live on web).

**How they talk to each other (important, and already wired for you):**
The browser only ever calls `https://studybuddy.mj665.in/api/...`. Vercel secretly forwards those `/api` calls to your Railway backend. This "same-origin proxy" is why login works without any messy cross-site cookie/CORS problems. You don't have to do anything special — `next.config.ts` already does it.

```
 Browser ──► studybuddy.mj665.in ──(/api/*)──► studybuddy-api.mj665.in ──► Neon Postgres
             (Vercel · frontend)   proxy         (Railway · backend)         (your database)
```

**Your database is already built** — Railway will just connect to it via `DATABASE_URL`. On every startup the backend automatically ensures your two admin logins exist (details in Part C).

---

## 1. What you need before starting

- [ ] A **Vercel** account (free) — https://vercel.com
- [ ] A **Railway** account (~$5/mo) — https://railway.com
- [ ] Your repo pushed to **GitHub** (both Vercel & Railway deploy from GitHub)
- [ ] Access to **DNS** for `mj665.in` (wherever you bought/manage the domain) — to point the two subdomains
- [ ] Your existing credentials from local `apps/api/.env`: `DATABASE_URL`, `GEMINI_API_KEY`, Resend key, AWS S3 keys, Upstash Redis. (You already run the app locally, so you have these.)

> If your code isn't on GitHub yet: create a repo on GitHub, then in the project folder run `git remote add origin <your-repo-url>` and `git push -u origin master`.

---

## PART A — Deploy the Backend (Railway)

The backend is a normal long-running server (it has a scheduler + background workers), so it needs Railway/Render/Fly — **not** Vercel. A `Dockerfile` and `railway.json` are already in `apps/api`, so Railway just builds and runs them.

### A1. Create the service
1. Go to https://railway.com → **New Project** → **Deploy from GitHub repo** → pick this repo.
2. Railway creates a service. Open it → **Settings**:
   - **Root Directory**: `apps/api`  ← *critical*, tells Railway where the Dockerfile is.
   - **Builder**: it will auto-detect **Dockerfile** (railway.json also declares this).
   - **Healthcheck Path**: `/health` (already set by railway.json).

### A2. Add the environment variables
Open the service → **Variables** → paste them in. Use `apps/api/.env.production.example` as your checklist. The essential ones:

```
ENVIRONMENT=production
DEBUG=false
RUN_SCHEDULER=true
ENFORCE_HTTPS=true

DATABASE_URL=<your existing Neon URL>

# generate each: openssl rand -hex 32
JWT_SECRET_KEY=<32-byte random hex>
HMAC_KEY_SECRET=<32-byte random hex>

APP_ADMIN_EMAIL=meet.jain563@gmail.com
APP_ADMIN_PASSWORD=Meet@123
LD_ADMIN_EMAIL=contact.hackathonmj@gmail.com
LD_ADMIN_PASSWORD=Contact@123
SEED_ORG_NAME=Sigmoid HQ
SEED_ORG_SLUG=sigmoid-hq

ALLOWED_ORIGINS=["https://studybuddy.mj665.in"]
FRONTEND_URL=https://studybuddy.mj665.in

GEMINI_API_KEY=<your key>
RESEND_EMAILS_API_KEY=<your key>

AWS_ACCESS_KEY_ID=<your key>
AWS_SECRET_ACCESS_KEY=<your key>
AWS_REGION=us-east-1
S3_BUCKET_NAME=<your bucket>

UPSTASH_REDIS_REST_URL=<your url>
UPSTASH_REDIS_REST_TOKEN=<your token>
```

> **The backend will refuse to start in production if any of these are missing:**
> `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ADMIN_PASSWORD`, `S3_BUCKET_NAME`,
> `GEMINI_API_KEY`, `ALLOWED_ORIGINS`, and `HMAC_KEY_SECRET` (must not be the dev
> default). This is a safety check, not a bug — fill them and it boots.
>
> To generate a secret on your Mac: open Terminal and run `openssl rand -hex 32`.

### A2b. Exactly what to change vs your existing local `.env`
You already have most values locally. Copy them over, then apply these **3 deltas** (your current local `.env` is wrong for production on these):

| Var | Your local `.env` now | Set to (production) | Why |
|-----|-----------------------|---------------------|-----|
| `DEBUG` | `TRUE` (and a duplicate `False`) | **`false`** | `DEBUG=true` leaks verbose errors and only allows `localhost` in CORS. Remove the duplicate line too. |
| `ALLOWED_ORIGINS` | *(missing)* | **`["https://studybuddy.mj665.in"]`** | Required once `DEBUG=false`; whitelists your web domain. |
| `FRONTEND_URL` | *(missing)* | **`https://studybuddy.mj665.in`** | Builds exam-invite email links + notification deep-links (`…/exam/{id}`). |

Everything else from your local `.env` carries over as-is (`DATABASE_URL`, `GEMINI_API_KEY`, `AWS_*`, `AWS_S3_BUCKET`, `UPSTASH_*`, `RESEND_*`, `JWT_SECRET_KEY`, `HMAC_KEY_SECRET`, the `*_ADMIN_*` seed vars). You can also drop the unused `NEO4J_*` lines — the KT store is Postgres/pgvector now.

### A3. Deploy + custom domain
1. Railway builds and deploys automatically. Watch **Deployments → Logs** until you see `Application startup complete`.
2. In **Settings → Networking → Custom Domain**, add `studybuddy-api.mj665.in`.
3. Railway shows you a **CNAME target** (like `xxxx.up.railway.app`). Add it to your DNS (see Part D).
4. Test: open `https://studybuddy-api.mj665.in/health` — you should see a small JSON "ok".

---

## PART B — Deploy the Frontend (Vercel)

### B1. Import the project
1. Go to https://vercel.com → **Add New… → Project** → import this GitHub repo.
2. In the setup screen:
   - **Root Directory**: click **Edit** → choose `apps/web-next`  ← *critical*.
   - **Framework Preset**: Next.js (auto-detected).
   - Leave Build/Output commands as default.

### B2. Environment variables (only one, and it's optional)
- `API_PROXY_ORIGIN = https://studybuddy-api.mj665.in`
  (Optional — the code already defaults to this. Set it only if the backend URL differs.)
- **Do NOT add `NEXT_PUBLIC_API_BASE`.** Leaving it unset is what makes the same-origin proxy work.

### B3. Deploy + custom domain
1. Click **Deploy**. Wait for the build to finish (it builds the 35 routes).
2. **Settings → Domains** → add `studybuddy.mj665.in`. Vercel shows a CNAME/A record for DNS (see Part D).
3. Open `https://studybuddy.mj665.in` → the login page should load.

---

## PART C — Your two admin logins (already automated)

You asked for these to live in env, be changeable by you, and be seeded into the DB. **That is exactly how it already works** — no code changes needed:

- The backend file `ensure_system_identity.py` runs on **every startup**. It reads
  `APP_ADMIN_EMAIL/PASSWORD` and `LD_ADMIN_EMAIL/PASSWORD` and **creates the accounts if missing, or updates their password/role to match** if they already exist.
- Because your database already has these two users, the seed will simply **enforce the passwords you set in Railway**.

So after deploy you can log in at `https://studybuddy.mj665.in` with **whatever you set** in these env vars:

| Role | Email (env var) | Password (env var) |
|------|-----------------|--------------------|
| App / Platform Admin | `APP_ADMIN_EMAIL` = `meet.jain563@gmail.com` | `APP_ADMIN_PASSWORD` |
| L&D Admin | `LD_ADMIN_EMAIL` = `contact.hackathonmj@gmail.com` | `LD_ADMIN_PASSWORD` |

> ⚠️ Heads-up: your current `.env` sets **`LD_ADMIN_PASSWORD=Meet@123`** (not `Contact@123`). Whatever you put in the env is what the L&D Admin login becomes — set it to what you actually want before deploying.

**To change a password later:** edit the value in Railway → **Variables** → the service redeploys → the new password is enforced on the next boot. (No database surgery needed.)

> Security note: these are real credentials. `Meet@123` / `Contact@123` are weak — fine to launch with, but change them in Railway to something stronger when convenient. They live only in Railway's Variables, never committed to git.

---

## PART D — DNS records (point your subdomains)

In your `mj665.in` DNS provider, add the two records the platforms gave you:

| Type | Name (host) | Value | From |
|------|-------------|-------|------|
| CNAME | `studybuddy-api` | `<the target Railway showed>` | Railway custom domain |
| CNAME | `studybuddy` | `cname.vercel-dns.com` (or the exact value Vercel showed) | Vercel domain |

DNS can take a few minutes to a couple of hours. Both platforms auto-issue HTTPS certificates once DNS resolves.

---

## PART D2 — Observability (Sentry now, OpenTelemetry later)

Errors, traces, logs, and metrics from **all three apps** (api, web, mobile) flow into **one Sentry project**, with alerts pushed to **Slack**. It's all env-driven and off by default (no DSN ⇒ nothing sends), so you turn it on by pasting a DSN.

### One-time setup
1. In Sentry (org `meet-w7`) create **one project** → copy its **DSN**.
2. Set the **same DSN** in all three places:
   - Railway (backend): `SENTRY_DSN=<dsn>` + `TELEMETRY_BACKEND=sentry` + `SENTRY_ENVIRONMENT=production`.
   - Vercel (web): `NEXT_PUBLIC_SENTRY_DSN=<dsn>`.
   - EAS (mobile): `EXPO_PUBLIC_SENTRY_DSN=<dsn>`.
3. For **source maps** (readable stack traces), set the build-time token in each platform: `SENTRY_ORG=meet-w7`, `SENTRY_PROJECT=studybuddy`, `SENTRY_AUTH_TOKEN=<your sntrys_… token>`.
4. **Slack:** in Sentry → Settings → Integrations → **Slack** → install & add it to a channel (e.g. `#alerts`). Then run the alert-rule script:
   ```bash
   export SENTRY_AUTH_TOKEN=sntrys_...  SENTRY_ORG=meet-w7  SENTRY_PROJECT=studybuddy  SLACK_CHANNEL='#alerts'
   python scripts/setup_sentry.py       # creates error-volume / new-issue / regression / crash rules → Slack
   ```
5. **Direct critical alerts:** create a Slack **Incoming Webhook** and set `SLACK_WEBHOOK_URL=<url>` on Railway. The backend posts terminal job failures, scheduler-task failures, and unhandled 500s straight to it.

### What you get (no extra hosting)
- **Errors**: every unhandled 500 (backend), React error boundary (web), native crash/JS error (mobile) — tagged by `component` (api/web/mobile) and user/org.
- **Traces**: request → DB → outbound-HTTP spans (backend); page loads + client navigations + **session replay on errors** (web); app performance (mobile).
- **Logs**: structured JSON logs (`LOG_FORMAT=json`) shipped to Sentry Logs.
- **Metrics** (ride on traces/logs — no metrics backend needed): `ai.cost_usd` / `ai.tokens.*` per feature+model, `job.duration` / `job.completed`, `task.run`, `http.request.duration`, `db.query.slow`.

### Switching to OpenTelemetry later (when you want)
No re-instrumentation — flip env on the backend:
```
TELEMETRY_BACKEND=otel
OTEL_EXPORTER_OTLP_ENDPOINT=https://<your-collector>
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer <token>
```
and on that deploy: `pip install -r apps/api/requirements-otel.txt`. The same spans/metrics/logs then export over OTLP to any collector (Grafana Cloud free tier, self-hosted, etc.). Sentry stays for the frontend/mobile until you migrate those too.

### Cost control
Errors are captured 100%; traces/profiles/replay are **sampled** (defaults 20% traces, 10% replay) via `SENTRY_TRACES_SAMPLE_RATE` etc. — lower them if you approach Sentry's free-tier quota.

---

## PART E — Final verification (once both are live)

1. `https://studybuddy-api.mj665.in/health` → JSON ok (backend alive).
2. `https://studybuddy.mj665.in` → login page loads.
3. Log in as the L&D Admin → dashboard loads (this proves the frontend→backend proxy + database all work end-to-end).
4. Open on your phone browser at 390px width → no sideways scrolling (mobile responsive).
5. Publish a test exam with your own email as a recipient → you get the invite email with a working link (proves Resend + `FRONTEND_URL`).
6. **Observability**: after setting the Sentry DSN, hit `https://studybuddy-api.mj665.in/sentry-debug` isn't wired — instead trigger any real error (or use Sentry's "Send test event" in the project onboarding). Confirm the event appears in Sentry and an alert lands in your Slack `#alerts` channel.

---

## What I need from you / things only you can do

I've written all the config files. These steps require **your** accounts/keys, so you do them (I can't):

1. **Push to GitHub** (if not already) and connect Vercel + Railway to it.
2. **Paste the env values** into Railway (Part A2) — especially your real `DATABASE_URL`, `GEMINI_API_KEY`, Resend key, AWS S3 keys, Upstash Redis (copy them from your local `apps/api/.env`).
3. **Generate `JWT_SECRET_KEY` and `HMAC_KEY_SECRET`** (`openssl rand -hex 32`) — don't reuse dev defaults.
4. **Add the two DNS records** for the subdomains.
5. Decide whether to keep `Meet@123` / `Contact@123` or set stronger passwords in Railway.

### Please tell me / confirm, so I can finish anything else:
- Do you have an **S3 bucket + AWS keys** ready? (Required for the backend to boot — KT/resource uploads use it.) If not, I can relax that requirement so it boots without S3.
- Is your **Redis** Upstash (REST url+token) or a `redis://` URL? Either works — just want to document the right one.
- Should I also finish the **mobile app** deploy (Expo/EAS build to an Android `.aab` for the Play Store) now, or after the website is live? (It needs `EXPO_PUBLIC_WEB_URL=https://studybuddy.mj665.in` + a Firebase `google-services.json` from you.)
- Do you want a **GitHub Actions** workflow so every push auto-deploys, or are Vercel/Railway's built-in GitHub auto-deploys enough? (They're enough for most people.)
