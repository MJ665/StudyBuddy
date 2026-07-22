'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'motion/react';
import {
  BrainCircuit,
  ChevronRight,
  Clock,
  RotateCcw,
  Target,
  Trophy,
} from 'lucide-react';
import { useAssessmentNav } from '@/lib/useAssessmentNav';
import { useSessionStore } from '@/stores/sessionStore';

/** Assessment result screen — moved out of the old app/page.tsx state machine. */
export default function AssessmentResultPage() {
  const router = useRouter();
  const { quiz } = useSessionStore();
  const { startBankQuiz } = useAssessmentNav();
  const result = quiz.result as {
    score: number;
    total: number;
    weighted_score?: number;
    total_weight?: number;
    timeTaken: number;
    breakdown?: Array<{
      question_text: string;
      user_answer?: string;
      correct_answer?: string;
      is_correct: boolean;
    }>;
  } | null;

  useEffect(() => {
    if (!result) router.replace('/dashboard');
  }, [result, router]);

  if (!result) return null;
  const bank = quiz.bank as { name?: string; id: number } | null;
  const accuracy = result.total > 0 ? Math.round((result.score / result.total) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      className="min-h-screen bg-slate-950 text-slate-200 flex items-center justify-center p-6"
    >
      <div className="w-full max-w-2xl">
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-10 shadow-2xl text-center mb-8 relative overflow-hidden">
          <div
            className={`absolute inset-0 opacity-5 pointer-events-none ${
              accuracy >= 70
                ? 'bg-gradient-to-br from-emerald-500 to-teal-500'
                : accuracy >= 40
                  ? 'bg-gradient-to-br from-amber-500 to-orange-500'
                  : 'bg-gradient-to-br from-rose-500 to-pink-500'
            }`}
          />

          <div
            className={`w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-6 text-4xl font-black border-4 ${
              accuracy >= 70
                ? 'border-emerald-500 bg-emerald-900/20 text-emerald-400'
                : accuracy >= 40
                  ? 'border-amber-500 bg-amber-900/20 text-amber-400'
                  : 'border-rose-500 bg-rose-900/20 text-rose-400'
            }`}
          >
            {accuracy}%
          </div>

          <h2 className="text-3xl font-bold text-white mb-2">Quiz Complete!</h2>
          <p className="text-slate-400 mb-8">{bank?.name || 'Assessment'}</p>

          <div className="grid grid-cols-4 gap-3 mb-8">
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <Trophy size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">
                {result.score}/{result.total}
              </p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Raw Score</p>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <BrainCircuit size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">
                {result.weighted_score?.toFixed(1) || '0.0'}/{result.total_weight?.toFixed(1) || '0.0'}
              </p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Weighted</p>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <Target size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">{accuracy}%</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Accuracy</p>
            </div>
            <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
              <Clock size={18} className="text-indigo-400 mx-auto mb-2" />
              <p className="text-xl font-bold text-white">
                {Math.floor(result.timeTaken / 60)}m {result.timeTaken % 60}s
              </p>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider mt-1">Time</p>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => bank && startBankQuiz(bank, quiz.questions.length)}
              className="flex-1 flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-bold transition-all border border-slate-700"
            >
              <RotateCcw size={18} /> Retake
            </button>
            <button
              onClick={() => router.push('/leaderboard')}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-xl font-bold transition-all shadow-lg shadow-indigo-500/30"
            >
              View Leaderboard <ChevronRight size={18} />
            </button>
          </div>
        </div>

        {result.breakdown && result.breakdown.length > 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl">
            <h3 className="font-bold text-white mb-4 text-lg">Answer Breakdown</h3>
            <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
              {result.breakdown.map((item, i) => (
                <div
                  key={i}
                  className={`p-4 rounded-xl border text-sm ${
                    item.is_correct
                      ? 'bg-emerald-900/10 border-emerald-500/20'
                      : 'bg-rose-900/10 border-rose-500/20'
                  }`}
                >
                  <p className="text-slate-300 font-medium mb-2">
                    {i + 1}. {item.question_text}
                  </p>
                  <div className="flex gap-4 flex-wrap mb-2">
                    <span
                      className={`text-xs font-bold px-2 py-1 rounded ${
                        item.is_correct
                          ? 'bg-emerald-900/30 text-emerald-400'
                          : 'bg-rose-900/30 text-rose-400'
                      }`}
                    >
                      Your: {item.user_answer || 'Skipped'}
                    </span>
                    {!item.is_correct && (
                      <span className="text-xs font-bold px-2 py-1 rounded bg-emerald-900/30 text-emerald-400">
                        Correct: {item.correct_answer}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
