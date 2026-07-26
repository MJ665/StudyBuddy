# StudyBuddy Web

The StudyBuddy frontend — **Next.js 15** (App Router), the marketing landing page, the full authenticated product, and an installable **PWA**. The same web app is what the [Android app](../mobile/README.md) renders in a WebView.

> Part of the [StudyBuddy monorepo](../../README.md). Backend: [`apps/api`](../api/README.md).

- **Next.js 15** · React 18 · **React Query** · **Tailwind v4** · `motion/react` · `lucide-react`
- Typed API client generated from the backend OpenAPI schema
- Dark, premium design system driven by CSS `@theme` tokens
- Error tracking via `@sentry/nextjs` (no-ops without a DSN)

---

## Routes & structure

App Router with route groups:

```
src/app/
  page.tsx                 "/"  → marketing landing (server-rendered) + AuthedRedirect island
  layout.tsx               root layout: fonts, providers (ReactQuery, Branding), PWA registrar
  manifest.ts              PWA manifest (start_url = /dashboard)
  (app)/                   AUTHENTICATED area — layout.tsx redirects to /login if no session
    dashboard · admin · mentor · group-admin · assessment/{run,result} · coding/{run,result}
    leaderboard · discussions · library · assignments · history · notifications · intel · resources
    profile · kt/[[...path]]   (KT hub — catch-all)
  (public)/                PUBLIC — login (email-first), forgot/reset password, profile/[slug]
  exam/[id] · exams · gradebook/[bankId] · platform · onboard · contact-me · privacy · terms
  global-error.tsx         root error boundary → Sentry
components/
  landing/                 marketing home (Hero, Products, Features, HowItWorks, Personas, CTA)
  ui/                      AppLayout, Sidebar, Toast, Skeleton, ConfirmationModal
  common/                  Branding, NotificationCenter, RichText, ActivityHeatmap
  <feature>/               dashboard, admin/tabs, mentor, kt, quiz, leaderboard, profile/tabs …
services/                  ApiService (legacy singleton) + api/ (typed openapi-fetch client)
stores/sessionStore.ts     Zustand: session + active-assessment state; landingRouteFor()
lib/                       useMobile, cn, ReactQueryProvider, viewRoutes
```

### Auth flow
- `(app)/layout.tsx` hydrates the session (`useSessionStore.hydrate()` → `GET /api/auth/me`) and redirects to `/login` if there's no session.
- `/login` redirects **already-authenticated** users to `landingRouteFor(user)` (`/dashboard`, `/admin`, `/mentor`, `/group-admin`).
- Transport: short-lived access token (Authorization header) bootstrapped/renewed via an **HttpOnly refresh cookie**.

---

## The `/api` proxy (why there's no CORS)

The browser only ever calls **`/api/*` on the web origin**; `next.config.ts` rewrites that to the real backend (`API_PROXY_ORIGIN`, default `https://studybuddy-api.mj665.in`). This keeps the refresh cookie **first-party** — no cross-site cookies, no CORS setup.

> **Do NOT set `NEXT_PUBLIC_API_BASE`** — leaving it unset keeps the client on the same-origin `/api` (see `src/services/apiShared.ts`). Setting it would bypass the proxy and break the cookie.

---

## Design system

Dark theme via CSS `@theme` tokens in `src/app/globals.css`:

```
--color-surface-dim: #0c1324           (app background)
--color-brand-primary-container: #8083ff   (indigo accent)
--color-brand-secondary: #4edea3       (emerald)
--color-on-surface: #dce1fb            (text)
```

Tailwind utilities are generated from these (`bg-surface-dim`, `text-on-surface-variant`, …). Fonts: Inter + Material Symbols. Animations: `motion/react`. Everything is **responsive down to 390px** (verified — no horizontal overflow), which is what the WebView app renders.

---

## Run & build

```bash
npm run dev            # http://localhost:3000 (proxies /api → http://127.0.0.1:8000)
npm run build          # production build
npx tsc --noEmit       # type-check
```

Requires the [backend](../api/README.md) running on `:8000` for API calls. Override the proxy target with `API_PROXY_ORIGIN`.

### Typed API client
`src/services/api/schema.d.ts` is generated from the backend OpenAPI schema (`docs/openapi.yaml`). Regenerate the schema with `apps/api/scripts/export_openapi.py`, then the openapi-fetch client in `src/services/api/` stays type-safe end to end.

---

## Environment

Template: [`.env.production.example`](.env.production.example) · Vercel-ready values: `.env.vercel` (gitignored).

```
API_PROXY_ORIGIN=https://studybuddy-api.mj665.in    # backend the /api proxy forwards to
NEXT_PUBLIC_SENTRY_DSN=...                           # optional; Sentry no-ops if unset
NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE=0.2
SENTRY_ORG / SENTRY_PROJECT / SENTRY_AUTH_TOKEN      # build-time source maps
# DO NOT set NEXT_PUBLIC_API_BASE
```

---

## PWA & the mobile app

- **PWA**: `manifest.ts` (`start_url = /dashboard`, standalone, maskable icons) + a service worker — installable "Add to Home Screen".
- **Mobile**: the [Expo app](../mobile/README.md) loads this deployed web app in a WebView, entering at `/dashboard` (not the marketing `/`). One codebase, three surfaces.

---

## Observability

`@sentry/nextjs` via `instrumentation.ts` + `instrumentation-client.ts` + `withSentryConfig` (source maps target the EU region, `de.sentry.io`). Session replay on errors, structured logs, and error boundaries (`(app)/error.tsx`, `(public)/error.tsx`, `global-error.tsx`) that capture to Sentry. All gated on `NEXT_PUBLIC_SENTRY_DSN`.

---

## Deployment

**Vercel** — Root Directory = `apps/web-next` (Framework auto-detects Next.js; output is `.next`). Add the domain, set `API_PROXY_ORIGIN` + Sentry vars. Full runbook: [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md).
