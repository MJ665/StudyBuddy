# StudyBuddy — Android app (`apps/mobile`)

A **thin Expo React Native shell** that renders the deployed web app (`apps/web-next`)
in a WebView. The web app is the **single master codebase** — anything pushed there
appears in the app instantly (the app just loads the live URL). This shell only adds
the native value Google Play expects from a real app: push notifications, offline
handling, hardware-back navigation, pull-to-refresh, splash screen, file uploads,
and external-link handling.

You can add real native screens later without a rewrite: this uses **expo-router**, so
`app/index.tsx` is the WebView and any new `app/<name>.tsx` becomes a native screen.

## One-time setup

```bash
# from repo root (npm workspaces)
npm install
cd apps/mobile
npx expo install --fix     # aligns native package versions with the Expo SDK
cp .env.example .env        # then edit EXPO_PUBLIC_WEB_URL etc.
```

Set in `.env` (or `eas.json` per build profile):

| Var | What |
|-----|------|
| `EXPO_PUBLIC_WEB_URL` | Deployed web app URL the WebView loads. For the Android **emulator** against a local `npm run dev` web server use `http://10.0.2.2:3000`. |
| `GOOGLE_SERVICES_JSON` | Path to Firebase `google-services.json` (see `google-services.json.example`). |
| `EAS_PROJECT_ID` | From `eas init`. |

## Run in development

```bash
# 1. Start the web app somewhere reachable (repo root):  npm run dev:next
# 2. Start the mobile app:
cd apps/mobile && npm start           # press "a" for Android emulator
```

The WebView loads `EXPO_PUBLIC_WEB_URL`. Login persists across restarts (DOM storage
+ cookies enabled). Android back navigates WebView history; airplane mode shows the
native offline screen; off-domain links open in the system browser.

## Push notifications (FCM)

Wired end-to-end:
- On login the injected bridge posts the auth token to the shell → the shell registers
  for an Expo push token and `POST`s it to the backend `POST /api/notifications/register-device`.
- Backend stores it (`device_tokens` table) and `send_push(user_id, title, body, url)`
  delivers via the Expo Push API (which routes to FCM on Android).
- Tapping a notification deep-links the WebView to the notification's `url`.

Requires the Firebase `google-services.json` (above) for production delivery.

## Ship to Google Play (one-shot approval checklist)

```bash
npm i -g eas-cli
eas login
eas init                              # sets EAS_PROJECT_ID
eas build -p android --profile production   # produces an .aab
eas submit -p android --profile production  # or upload the .aab manually
```

Before submitting, in the Play Console:
- **Privacy policy URL** → `https://<your-web>/privacy` (page added in the web app).
- **Data safety** form → email + usage data, encrypted in transit, not sold.
- **Account deletion** → the web app exposes account deletion (Settings) — link it.
- **App content / content rating** questionnaire.
- **Store listing** → icon (auto from `assets/icon.png`), feature graphic, and phone
  screenshots (capture the responsive web app running in the app).
- Minimum-functionality: push + offline + native nav + splash satisfy the "not just a
  webview" bar.

## Structure

```
apps/mobile/
  app.config.ts         # Expo config (env-driven: web URL, FCM, EAS id)
  eas.json              # build profiles (development/preview/production AAB)
  app/
    _layout.tsx         # expo-router root + notification handler
    index.tsx           # the WebView screen (all native add-ons)
  src/
    lib/push.ts         # FCM token registration + backend device registration
    components/OfflineScreen.tsx
  assets/               # icon / adaptive-icon / splash / notification icon (from web logo)
```
