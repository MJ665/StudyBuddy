import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import * as Sentry from '@sentry/react-native';

/**
 * Registers this device for FCM push (via Expo's push service) and returns the
 * Expo push token, or null if unavailable (simulator / denied permission).
 */
export async function registerForPushToken(): Promise<string | null> {
  if (!Device.isDevice) return null;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Default',
      importance: Notifications.AndroidImportance.DEFAULT,
      lightColor: '#8083ff',
    });
  }

  const existing = await Notifications.getPermissionsAsync();
  let status = existing.status;
  if (status !== 'granted') {
    const req = await Notifications.requestPermissionsAsync();
    status = req.status;
  }
  if (status !== 'granted') return null;

  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ??
    Constants?.easConfig?.projectId;
  try {
    const token = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    return token.data;
  } catch (err) {
    Sentry.captureException(err);
    return null;
  }
}

/**
 * Sends the device push token to the backend, associated with the logged-in
 * user. Called after the web layer signals a successful auth (via the WebView
 * bridge). Uses the deployed API base derived from the web URL.
 */
export async function registerDeviceWithBackend(
  webUrl: string,
  pushToken: string,
  authToken?: string,
): Promise<void> {
  const base = webUrl.replace(/\/$/, '');
  try {
    await fetch(`${base}/api/notifications/register-device`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      // The WebView shares cookies with the same origin; include them too.
      body: JSON.stringify({ token: pushToken, platform: Platform.OS }),
    });
  } catch (err) {
    // Non-fatal: push registration is best-effort — record for visibility.
    Sentry.captureException(err);
  }
}
