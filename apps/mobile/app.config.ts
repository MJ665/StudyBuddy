import type { ExpoConfig } from 'expo/config';

/**
 * StudyBuddy Android wrapper — a thin Expo shell that renders the deployed web
 * app (apps/web-next) in a WebView. The web app is the single master codebase;
 * anything pushed there reflects here instantly.
 *
 * Everything env-driven so nothing is hardcoded before hosting exists:
 *   EXPO_PUBLIC_WEB_URL  — the deployed web app URL the WebView loads
 *   GOOGLE_SERVICES_JSON — path to the Firebase google-services.json (for FCM)
 *   EAS_PROJECT_ID       — your EAS project id (from `eas init`)
 */
const WEB_URL = process.env.EXPO_PUBLIC_WEB_URL ?? 'https://REPLACE_ME.studybuddy.app';

const config: ExpoConfig = {
  name: 'StudyBuddy',
  slug: 'studybuddy',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  scheme: 'studybuddy',
  userInterfaceStyle: 'dark',
  backgroundColor: '#0c1324',
  assetBundlePatterns: ['**/*'],
  android: {
    package: 'com.studybuddy.app',
    versionCode: 1,
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#0c1324',
    },
    permissions: [
      'INTERNET',
      'POST_NOTIFICATIONS',
      'CAMERA',
      'READ_MEDIA_IMAGES',
      'READ_MEDIA_VIDEO',
    ],
    // Firebase config for FCM push. Owner drops google-services.json here (or
    // points GOOGLE_SERVICES_JSON at an EAS secret file).
    googleServicesFile: process.env.GOOGLE_SERVICES_JSON ?? './google-services.json',
  },
  plugins: [
    'expo-router',
    [
      'expo-splash-screen',
      {
        image: './assets/splash-icon.png',
        imageWidth: 200,
        resizeMode: 'contain',
        backgroundColor: '#0c1324',
      },
    ],
    [
      'expo-notifications',
      {
        icon: './assets/notification-icon.png',
        color: '#8083ff',
      },
    ],
    // Sentry — native crash handling + JS errors + source-map upload on EAS builds.
    // authToken comes from SENTRY_AUTH_TOKEN in the build env (never hardcode it).
    [
      '@sentry/react-native/expo',
      {
        organization: process.env.SENTRY_ORG ?? 'meet-w7',
        project: process.env.SENTRY_PROJECT ?? 'studybuddy',
      },
    ],
  ],
  extra: {
    webUrl: WEB_URL,
    sentryDsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
    eas: { projectId: process.env.EAS_PROJECT_ID ?? 'REPLACE_WITH_EAS_PROJECT_ID' },
  },
};

export default config;
