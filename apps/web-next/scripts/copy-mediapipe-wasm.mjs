// Copies MediaPipe Tasks Vision WASM from node_modules into public/ so the exam
// proctoring face-detector is self-hosted (no CDN dependency on the exam's
// critical path, works in the mobile WebView). Runs on predev/prebuild.
// The WASM (~32MB) is gitignored and regenerated here; the small .tflite model
// is committed under public/mediapipe/models/.
import { existsSync, mkdirSync, cpSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(__dirname, '..');
const dest = resolve(webRoot, 'public/mediapipe/wasm');

// The package's "exports" map blocks require.resolve of internal paths, so
// locate the wasm dir by the known node_modules layouts (local or hoisted to
// the workspace root).
const candidates = [
  resolve(webRoot, 'node_modules/@mediapipe/tasks-vision/wasm'),
  resolve(webRoot, '../../node_modules/@mediapipe/tasks-vision/wasm'),
];

try {
  const src = candidates.find((p) => existsSync(p));
  if (!src) {
    console.warn('[mediapipe] wasm source not found in', candidates, '— skipping (face detection will fall back).');
    process.exit(0);
  }
  mkdirSync(dest, { recursive: true });
  cpSync(src, dest, { recursive: true });
  console.log('[mediapipe] copied WASM →', dest);
} catch (err) {
  // Never fail the build over this — detection falls back to the browser API.
  console.warn('[mediapipe] copy skipped:', err?.message || err);
  process.exit(0);
}
