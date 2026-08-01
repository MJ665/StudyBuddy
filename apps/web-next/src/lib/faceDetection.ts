/**
 * Cross-browser face-presence detection for exam proctoring.
 *
 * Uses MediaPipe Tasks Vision (WASM) with a self-hosted model, so detection
 * works in Firefox/Safari/Android-WebView — not just Chromium's experimental
 * FaceDetector. Everything is loaded client-side and lazily (dynamic import),
 * so it never runs during SSR. Any load failure resolves to `null` and the
 * caller falls back to the browser FaceDetector (or video-only review).
 *
 * Assets are served from /public (see public/mediapipe/*), so the exam's
 * critical path has no third-party CDN dependency.
 */
export interface FacePresenceDetector {
  /** Number of faces currently visible in the video frame. */
  count(video: HTMLVideoElement): number;
  close(): void;
}

const WASM_PATH = '/mediapipe/wasm';
const MODEL_PATH = '/mediapipe/models/blaze_face_short_range.tflite';

/**
 * Build a MediaPipe face detector. Returns null if the model/WASM can't load
 * (offline, unsupported, asset missing) so the caller can fall back.
 */
export async function createFacePresenceDetector(): Promise<FacePresenceDetector | null> {
  if (typeof window === 'undefined') return null;
  try {
    const vision = await import('@mediapipe/tasks-vision');
    const fileset = await vision.FilesetResolver.forVisionTasks(WASM_PATH);
    const detector = await vision.FaceDetector.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_PATH },
      runningMode: 'VIDEO',
      minDetectionConfidence: 0.5,
    });

    return {
      count(video: HTMLVideoElement): number {
        if (!video.videoWidth) return -1; // frame not ready — caller ignores
        try {
          const res = detector.detectForVideo(video, performance.now());
          return res?.detections?.length ?? 0;
        } catch {
          return -1;
        }
      },
      close() {
        try { detector.close(); } catch { /* noop */ }
      },
    };
  } catch {
    return null;
  }
}
