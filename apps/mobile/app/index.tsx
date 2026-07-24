import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  BackHandler,
  Linking,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';
import type { WebViewNavigation } from 'react-native-webview';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import * as SplashScreen from 'expo-splash-screen';
import NetInfo from '@react-native-community/netinfo';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { OfflineScreen } from '@/components/OfflineScreen';
import { registerDeviceWithBackend, registerForPushToken } from '@/lib/push';

SplashScreen.preventAutoHideAsync().catch(() => {});

const WEB_URL: string =
  (Constants.expoConfig?.extra as { webUrl?: string } | undefined)?.webUrl ??
  'https://REPLACE_ME.studybuddy.app';
const WEB_HOST = safeHost(WEB_URL);

// Injected into the page: surfaces the auth token (localStorage 'study_token')
// to the native layer so we can register this device for push against the
// logged-in user. Zero web-app changes required. If the web app renames the
// token key, update it here.
const INJECTED_JS = `
(function () {
  var last = null;
  function report() {
    try {
      var t = window.localStorage.getItem('study_token');
      if (t && t !== last) {
        last = t;
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'AUTH', token: t }));
      }
    } catch (e) {}
  }
  report();
  setInterval(report, 3000);
})();
true;
`;

export default function WebAppScreen() {
  const webRef = useRef<WebView>(null);
  const insets = useSafeAreaInsets();
  const [canGoBack, setCanGoBack] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [online, setOnline] = useState(true);
  const [authToken, setAuthToken] = useState<string | null>(null);

  // ── Connectivity ──
  useEffect(() => {
    const unsub = NetInfo.addEventListener((s) => setOnline(!!s.isConnected));
    return () => unsub();
  }, []);

  // ── Android hardware back → WebView history ──
  useEffect(() => {
    if (Platform.OS !== 'android') return;
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (canGoBack) {
        webRef.current?.goBack();
        return true;
      }
      return false; // let the OS exit the app
    });
    return () => sub.remove();
  }, [canGoBack]);

  // ── Notification tap → deep-link into the WebView ──
  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener((resp) => {
      const url = (resp.notification.request.content.data as { url?: string })?.url;
      if (url && webRef.current) {
        const target = url.startsWith('http') ? url : `${WEB_URL.replace(/\/$/, '')}${url}`;
        webRef.current.injectJavaScript(`window.location.href=${JSON.stringify(target)}; true;`);
      }
    });
    return () => sub.remove();
  }, []);

  // ── Register for push once we have an auth token ──
  useEffect(() => {
    if (!authToken) return;
    let cancelled = false;
    (async () => {
      const pushToken = await registerForPushToken();
      if (!pushToken || cancelled) return;
      await registerDeviceWithBackend(WEB_URL, pushToken, authToken);
    })();
    return () => {
      cancelled = true;
    };
  }, [authToken]);

  const onMessage = useCallback((e: WebViewMessageEvent) => {
    try {
      const msg = JSON.parse(e.nativeEvent.data);
      if (msg?.type === 'AUTH' && msg.token) setAuthToken(msg.token);
    } catch {
      /* ignore non-JSON messages */
    }
  }, []);

  // ── Keep app-domain links in the WebView; open everything else externally ──
  const onShouldStart = useCallback((req: WebViewNavigation) => {
    const host = safeHost(req.url);
    if (req.url.startsWith('http') && host && WEB_HOST && host !== WEB_HOST) {
      Linking.openURL(req.url).catch(() => {});
      return false;
    }
    return true;
  }, []);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    webRef.current?.reload();
    setTimeout(() => setRefreshing(false), 800);
  }, []);

  if (!online) {
    return <OfflineScreen onRetry={() => NetInfo.fetch().then((s) => setOnline(!!s.isConnected))} />;
  }

  return (
    <View style={[styles.fill, { paddingTop: insets.top, backgroundColor: '#0c1324' }]}>
      <ScrollView
        contentContainerStyle={styles.fill}
        // ScrollView only exists to host pull-to-refresh; the WebView owns scroll.
        scrollEnabled={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#8083ff" />
        }
      >
        <WebView
          ref={webRef}
          source={{ uri: WEB_URL }}
          originWhitelist={['*']}
          injectedJavaScript={INJECTED_JS}
          onMessage={onMessage}
          onShouldStartLoadWithRequest={onShouldStart}
          onNavigationStateChange={(nav) => setCanGoBack(nav.canGoBack)}
          onLoadEnd={() => {
            setLoading(false);
            SplashScreen.hideAsync().catch(() => {});
          }}
          onError={() => setLoading(false)}
          // Persistence + storage so login survives restarts.
          javaScriptEnabled
          domStorageEnabled
          sharedCookiesEnabled
          thirdPartyCookiesEnabled
          // File uploads (KT documents) + media capture.
          allowFileAccess
          allowsInlineMediaPlayback
          mediaCapturePermissionGrantType="grant"
          setSupportMultipleWindows={false}
          style={{ backgroundColor: '#0c1324' }}
        />
      </ScrollView>

      {loading && (
        <View style={styles.loader} pointerEvents="none">
          <ActivityIndicator size="large" color="#8083ff" />
        </View>
      )}
    </View>
  );
}

function safeHost(url: string): string | null {
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  loader: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0c1324',
  },
});
