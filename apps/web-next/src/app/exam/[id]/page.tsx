'use client';

import 'katex/dist/katex.min.css';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import ApiService from '@/services/ApiService';
import QuestionCard, { QCard } from '@/components/quiz/cards/QuestionCard';
import { uploadProctorMedia } from '@/lib/proctorMedia';
import { createFacePresenceDetector, type FacePresenceDetector } from '@/lib/faceDetection';

interface ExamSettings {
  require_camera: boolean;
  record_video: boolean;
  require_fullscreen: boolean;
  max_tab_switches: number;
  negative_marking: number;
  allow_backtrack: boolean;
  show_results_immediately: boolean;
  instructions: string;
}
interface Paper {
  attempt_id: number;
  title: string;
  proctoring_mode: string;
  duration_minutes?: number;
  deadline: string;
  window_label?: string | null;
  settings?: Partial<ExamSettings>;
  questions: QCard[];
}
interface Result {
  score?: number; total?: number; percent?: number; passed?: boolean;
  status: string; flags?: number; results_withheld?: boolean;
}

const DEFAULTS: ExamSettings = {
  require_camera: false, record_video: false, require_fullscreen: false,
  max_tab_switches: 0, negative_marking: 0, allow_backtrack: true,
  show_results_immediately: true, instructions: '',
};

function fmtTime(ms: number): string {
  if (ms < 0) ms = 0;
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

export default function ExamRunnerPage() {
  const params = useParams();
  const examId = Number(Array.isArray(params.id) ? params.id[0] : params.id);

  const [paper, setPaper] = useState<Paper | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<number>(0);
  const [flags, setFlags] = useState<number>(0);
  const [phase, setPhase] = useState<'lobby' | 'running'>('lobby');
  const [camStatus, setCamStatus] = useState<'idle' | 'live' | 'no_face' | 'multiple' | 'denied'>('idle');
  const [starting, setStarting] = useState(false);
  const [qIdx, setQIdx] = useState(0); // linear-mode cursor (allow_backtrack=false)
  const [fullscreenLost, setFullscreenLost] = useState(false);
  const submittingRef = useRef(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const tabSwitchesRef = useRef(0);

  const settings: ExamSettings = { ...DEFAULTS, ...(paper?.settings || {}) };
  const webcamNeeded = !!paper && paper.proctoring_mode !== 'none' &&
    (settings.require_camera || settings.record_video || paper.proctoring_mode === 'advanced');

  // Load the paper (start attempt on the server).
  useEffect(() => {
    ApiService.startExam(examId)
      .then((p: Paper) => setPaper(p))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Could not start exam'));
  }, [examId]);

  const submit = useCallback(async () => {
    if (!paper || submittingRef.current || result) return;
    submittingRef.current = true;
    try {
      const r = await ApiService.submitExam(paper.attempt_id, answers);
      setResult(r);
      // Release camera + fullscreen on finish.
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submit failed');
      submittingRef.current = false;
    }
  }, [paper, answers, result]);

  // Countdown → auto-submit at deadline.
  useEffect(() => {
    if (!paper || result || phase !== 'running') return;
    const dl = new Date(paper.deadline).getTime();
    const t = setInterval(() => {
      const rem = dl - Date.now();
      setRemaining(rem);
      if (rem <= 0) { clearInterval(t); submit(); }
    }, 1000);
    return () => clearInterval(t);
  }, [paper, result, phase, submit]);

  // Integrity listeners (tab/copy/paste/focus/fullscreen) once running.
  useEffect(() => {
    if (!paper || result || phase !== 'running' || paper.proctoring_mode === 'none') return;
    const flag = (event_type: string, detail?: string) => {
      setFlags((f) => f + 1);
      ApiService.logProctorEvent(paper.attempt_id, event_type, detail).catch(() => {});
    };
    const onVis = () => {
      if (!document.hidden) return;
      tabSwitchesRef.current += 1;
      flag('tab_switch', `Tab switch #${tabSwitchesRef.current}`);
      // Auto-submit when the tab-switch budget is exceeded (Mettl-style).
      if (settings.max_tab_switches > 0 && tabSwitchesRef.current > settings.max_tab_switches) {
        setError('Exam auto-submitted: tab-switch limit exceeded.');
        submit();
      }
    };
    const onBlur = () => flag('focus_loss');
    const onCopy = () => flag('copy');
    const onPaste = () => flag('paste');
    const onFsChange = () => {
      if (!settings.require_fullscreen) return;
      if (!document.fullscreenElement) {
        flag('fullscreen_exit', 'Left fullscreen');
        setFullscreenLost(true);   // show the blocking "return to fullscreen" prompt
      } else {
        setFullscreenLost(false);
      }
    };
    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('blur', onBlur);
    document.addEventListener('copy', onCopy);
    document.addEventListener('paste', onPaste);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('paste', onPaste);
      document.removeEventListener('fullscreenchange', onFsChange);
    };
  }, [paper, result, phase, settings.max_tab_switches, settings.require_fullscreen, submit]);

  // Bind the captured stream to the <video> once the running preview mounts.
  // The camera is acquired in the lobby (startExam) where NO <video> exists yet,
  // so without this the preview would render black. Rebinds whenever the element
  // remounts (lobby→running, preview↔hidden swap).
  useEffect(() => {
    if (phase !== 'running' || !webcamNeeded) return;
    const v = videoRef.current;
    const s = streamRef.current;
    if (v && s && v.srcObject !== s) {
      v.srcObject = s;
      v.play().catch(() => {});
    }
  });

  // Webcam pipeline: face-presence detection + periodic snapshots (→S3) +
  // continuous video recording (→S3) once running.
  useEffect(() => {
    if (!paper || result || phase !== 'running' || !webcamNeeded) return;
    const stream = streamRef.current;
    if (!stream) return;
    let snapTimer: ReturnType<typeof setInterval> | null = null;
    let faceTimer: ReturnType<typeof setInterval> | null = null;
    let recorder: MediaRecorder | null = null;
    let lastFaceFlag = '';
    const aid = paper.attempt_id;

    const flagFace = (event_type: string, detail: string) => {
      ApiService.logProctorEvent(aid, event_type, detail).catch(() => {});
      setFlags((f) => f + 1);
    };

    const snapshotBlob = async (max = 480, quality = 0.6): Promise<Blob | null> => {
      const v = videoRef.current;
      if (!v || !v.videoWidth) return null;
      const scale = Math.min(1, max / v.videoWidth);
      const c = document.createElement('canvas');
      c.width = Math.round(v.videoWidth * scale);
      c.height = Math.round(v.videoHeight * scale);
      const ctx = c.getContext('2d');
      if (!ctx) return null;
      ctx.drawImage(v, 0, 0, c.width, c.height);
      return new Promise((resolve) => c.toBlob((b) => resolve(b), 'image/jpeg', quality));
    };

    // Periodic snapshot every 15s → S3 (data-URL fallback if S3 absent).
    snapTimer = setInterval(async () => {
      const b = await snapshotBlob();
      if (b) uploadProctorMedia(aid, b, { eventType: 'webcam_snapshot', filename: `snap_${Date.now()}.jpg`, detail: 'periodic' });
    }, 15000);

    // Continuous video recording → 20s chunks → S3.
    if (settings.record_video && typeof MediaRecorder !== 'undefined') {
      try {
        const mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
          .find((m) => MediaRecorder.isTypeSupported(m)) || 'video/webm';
        recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 300_000 });
        recorder.ondataavailable = (ev) => {
          if (ev.data && ev.data.size > 0) {
            uploadProctorMedia(aid, ev.data, { eventType: 'video_chunk', filename: `vid_${Date.now()}.webm`, detail: 'recording' });
          }
        };
        recorder.start(20000); // fire ondataavailable every 20s
      } catch { /* recording unsupported — snapshots still cover it */ }
    }

    // Face-presence detection. Prefer the real MediaPipe model (cross-browser);
    // fall back to Chromium's experimental FaceDetector; else video-only review.
    let mpDetector: FacePresenceDetector | null = null;
    let disposed = false;

    const onCount = (n: number) => {
      if (n < 0) return; // frame not ready / hiccup
      if (n === 0) {
        setCamStatus('no_face');
        if (lastFaceFlag !== 'no_face') { flagFace('no_face', 'No face detected in webcam'); lastFaceFlag = 'no_face'; }
      } else if (n > 1) {
        setCamStatus('multiple');
        if (lastFaceFlag !== 'multiple') { flagFace('multiple_faces', `${n} faces detected`); lastFaceFlag = 'multiple'; }
      } else {
        setCamStatus('live'); lastFaceFlag = '';
      }
    };

    (async () => {
      mpDetector = await createFacePresenceDetector();
      if (disposed) { mpDetector?.close(); return; }
      if (mpDetector) {
        faceTimer = setInterval(() => {
          const v = videoRef.current;
          if (!v || !v.videoWidth || !mpDetector) return;
          onCount(mpDetector.count(v));
        }, 3000);
        return;
      }
      // Fallback: Chromium FaceDetector.
      const FD = (window as unknown as { FaceDetector?: new (o?: unknown) => { detect: (v: unknown) => Promise<unknown[]> } }).FaceDetector;
      const detector = FD ? new FD({ fastMode: true, maxDetectedFaces: 5 }) : null;
      if (detector) {
        faceTimer = setInterval(async () => {
          const v = videoRef.current;
          if (!v || !v.videoWidth) return;
          try {
            const faces = await detector.detect(v);
            onCount(Array.isArray(faces) ? faces.length : 0);
          } catch { /* detection hiccup */ }
        }, 4000);
      }
    })();

    return () => {
      disposed = true;
      if (snapTimer) clearInterval(snapTimer);
      if (faceTimer) clearInterval(faceTimer);
      mpDetector?.close();
      try { recorder?.state !== 'inactive' && recorder?.stop(); } catch { /* noop */ }
    };
  }, [paper, result, phase, webcamNeeded, settings.record_video]);

  // ── Start (from lobby): acquire camera + fullscreen, then run ──────────────
  const startExam = async () => {
    if (!paper) return;
    setStarting(true);
    setError(null);
    try {
      if (webcamNeeded) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
          streamRef.current = stream;
          if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => {}); }
          setCamStatus('live');
        } catch {
          setCamStatus('denied');
          if (settings.require_camera) {
            setError('This exam requires camera access. Please allow the camera and try again.');
            setStarting(false);
            return;
          }
        }
      }
      if (settings.require_fullscreen) {
        try { await document.documentElement.requestFullscreen(); } catch { /* user can still proceed */ }
      }
      setPhase('running');
    } finally {
      setStarting(false);
    }
  };

  if (error && phase === 'lobby') return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="text-rose-400 mb-4">{error}</div>
        <a href="/exams" className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">← Back to exams</a>
      </div>
    </div>
  );
  if (error) return <div className="min-h-screen bg-slate-950 text-rose-400 flex items-center justify-center p-8">{error}</div>;
  if (!paper) return <div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center">Preparing exam…</div>;

  if (result) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          {result.results_withheld ? (
            <>
              <div className="text-3xl font-black mb-2 text-emerald-400">Submitted ✓</div>
              <div className="text-slate-400 text-sm">Your responses were recorded. Results will be shared by your L&amp;D team.</div>
            </>
          ) : (
            <>
              <div className={`text-5xl font-black mb-2 ${result.passed ? 'text-emerald-400' : 'text-rose-400'}`}>{result.percent}%</div>
              <div className="text-xl font-bold mb-4">{result.passed ? 'Passed' : 'Not passed'}</div>
              <div className="text-slate-400 text-sm">Score {result.score}/{result.total} · status {result.status} · {result.flags} integrity flag(s)</div>
            </>
          )}
          <div className="mt-6"><a href="/exams" className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm">← Back to exams</a></div>
        </div>
      </div>
    );
  }

  // ── Pre-exam lobby ─────────────────────────────────────────────────────────
  if (phase === 'lobby') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
        <div className="max-w-lg w-full rounded-2xl bg-slate-900 border border-slate-800 p-8">
          <h1 className="text-2xl font-black mb-1">{paper.title}</h1>
          <p className="text-slate-400 text-sm mb-5">Proctored exam · Powered by StudyBuddy</p>

          <div className="grid grid-cols-2 gap-3 text-sm mb-5">
            <div className="rounded-lg bg-slate-800/60 p-3"><div className="text-slate-500 text-[11px] uppercase tracking-widest">Questions</div><div className="font-bold">{paper.questions.length}</div></div>
            <div className="rounded-lg bg-slate-800/60 p-3"><div className="text-slate-500 text-[11px] uppercase tracking-widest">Duration</div><div className="font-bold">{paper.duration_minutes ?? Math.round((new Date(paper.deadline).getTime() - Date.now()) / 60000)} min</div></div>
            {paper.window_label && <div className="col-span-2 rounded-lg bg-slate-800/60 p-3"><div className="text-slate-500 text-[11px] uppercase tracking-widest">Window</div><div className="font-bold">🗓️ {paper.window_label}</div></div>}
          </div>

          {settings.instructions && (
            <div className="rounded-lg bg-indigo-500/10 border border-indigo-500/20 p-4 mb-5 text-sm text-slate-300 whitespace-pre-wrap">{settings.instructions}</div>
          )}

          <ul className="text-xs text-slate-400 space-y-1 mb-6">
            {webcamNeeded && <li>📷 This exam is webcam-proctored{settings.record_video ? ' and your session will be recorded' : ''}. Leaving frame / a second person is flagged.</li>}
            {settings.require_fullscreen && <li>🖥️ Fullscreen is required. Exiting fullscreen is flagged.</li>}
            {settings.max_tab_switches > 0 && <li>🔁 Max {settings.max_tab_switches} tab-switch(es) — exceeding auto-submits your exam.</li>}
            {settings.negative_marking > 0 && <li>➖ Negative marking: {settings.negative_marking} of the points per wrong answer.</li>}
            <li>⏱️ The timer starts when you click Start and cannot be paused.</li>
          </ul>

          {error && <div className="rounded-lg bg-rose-500/10 text-rose-400 p-3 text-sm mb-4">{error}</div>}
          <button onClick={startExam} disabled={starting} className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 py-3 font-bold">
            {starting ? 'Preparing…' : 'Start exam'}
          </button>
        </div>
      </div>
    );
  }

  const camActive = webcamNeeded && phase === 'running';
  const camBadge =
    camStatus === 'no_face' ? { text: 'No face — stay in frame', cls: 'bg-amber-500/90' }
    : camStatus === 'multiple' ? { text: 'Multiple faces detected', cls: 'bg-rose-500/90' }
    : camStatus === 'denied' ? { text: 'Camera blocked', cls: 'bg-rose-600/90' }
    : { text: settings.record_video ? 'Recording' : 'Monitoring', cls: 'bg-emerald-500/90' };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Blocking overlay: force the candidate back into fullscreen (not just a flag) */}
      {fullscreenLost && phase === 'running' && !result && (
        <div className="fixed inset-0 z-50 bg-slate-950/95 flex items-center justify-center p-6">
          <div className="max-w-sm text-center">
            <div className="text-4xl mb-3">🖥️</div>
            <h2 className="text-xl font-black mb-2">Return to fullscreen to continue</h2>
            <p className="text-slate-400 text-sm mb-5">This exam must run in fullscreen. Leaving it has been flagged for the proctor.</p>
            <button
              onClick={async () => { try { await document.documentElement.requestFullscreen(); setFullscreenLost(false); } catch { /* user gesture required */ } }}
              className="px-5 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 font-bold"
            >
              Re-enter fullscreen
            </button>
          </div>
        </div>
      )}
      {camActive && (
        <div className="fixed bottom-4 right-4 z-30 w-40 rounded-xl overflow-hidden border-2 border-slate-700 shadow-2xl bg-black">
          <video ref={videoRef} muted playsInline className="w-full h-28 object-cover scale-x-[-1]" />
          <div className={`text-[10px] font-bold text-white text-center py-1 ${camBadge.cls}`}>{camBadge.text}</div>
        </div>
      )}
      {!camActive && <video ref={videoRef} className="hidden" muted playsInline />}

      <div className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur border-b border-slate-800">
        <div className="max-w-3xl mx-auto flex items-center justify-between px-5 py-3">
          <div className="font-bold truncate">{paper.title}</div>
          <div className="flex items-center gap-4 text-sm">
            {flags > 0 && <span className="text-amber-400">⚠ {flags} flag{flags > 1 ? 's' : ''}</span>}
            <span className={`font-mono font-bold ${remaining < 60000 ? 'text-rose-400' : 'text-emerald-400'}`}>{fmtTime(remaining)}</span>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto p-5">
        {settings.allow_backtrack ? (
          <>
            {paper.questions.map((q, i) => (
              <QuestionCard
                key={q.id}
                q={q}
                index={i}
                value={answers[String(q.id)] ?? (q.question_type === 'mcq_multi' ? [] : '')}
                onChange={(v) => setAnswers((a) => ({ ...a, [String(q.id)]: v }))}
              />
            ))}
            <button onClick={submit} className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-3 font-bold mt-2">Submit exam</button>
          </>
        ) : (
          // Linear mode: one question at a time, no going back (allow_backtrack=false).
          <>
            <div className="text-xs text-slate-500 mb-2">Question {qIdx + 1} of {paper.questions.length} · you cannot return to previous questions</div>
            {paper.questions[qIdx] && (
              <QuestionCard
                key={paper.questions[qIdx].id}
                q={paper.questions[qIdx]}
                index={qIdx}
                value={answers[String(paper.questions[qIdx].id)] ?? (paper.questions[qIdx].question_type === 'mcq_multi' ? [] : '')}
                onChange={(v) => setAnswers((a) => ({ ...a, [String(paper.questions[qIdx].id)]: v }))}
              />
            )}
            {qIdx < paper.questions.length - 1 ? (
              <button onClick={() => setQIdx((i) => Math.min(i + 1, paper.questions.length - 1))} className="w-full rounded-lg bg-indigo-600 hover:bg-indigo-500 py-3 font-bold mt-2">Next question →</button>
            ) : (
              <button onClick={submit} className="w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 py-3 font-bold mt-2">Submit exam</button>
            )}
          </>
        )}
        <p className="text-center text-slate-600 text-xs mt-4">Powered by StudyBuddy</p>
      </div>
    </div>
  );
}
