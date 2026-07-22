import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { XCircle, Trophy, Sparkles, Send, BrainCircuit, Timer } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

export default function DailyChallengeModal({ challenge, onClose, onSuccess }: any) {
  const { toast } = useToast();
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);

  const question = challenge.question;

  const handleSubmit = async () => {
    if (!selectedOption) return;
    
    setIsSubmitting(true);
    try {
      const payload = {
        bank_id: question.bank_id,
        is_daily_challenge: true,
        answers: [
          {
            question_id: question.id,
            user_answer: selectedOption
          }
        ]
      };
      
      const res = await ApiService.submitAttempt(payload);
      setResult(res);
      if (onSuccess) onSuccess(res);
    } catch (err: any) {
      toast.error(err.message);
    } finally {

      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
        className="relative w-full max-w-lg bg-white dark:bg-gray-900 rounded-3xl shadow-2xl overflow-hidden border border-gray-100 dark:border-gray-800"
      >
        {/* Header decoration */}
        <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-500 opacity-10 dark:opacity-20" />
        
        <div className="p-8 relative">
          <div className="flex justify-between items-start mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-indigo-100 dark:bg-indigo-900/40 rounded-2xl text-indigo-600 dark:text-indigo-400">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-black text-gray-900 dark:text-white">Daily Challenge</h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs font-semibold px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-full">
                    {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                    question.difficulty === 'Hard' ? 'bg-red-100 text-red-600' : 
                    question.difficulty === 'Medium' ? 'bg-amber-100 text-amber-600' : 'bg-green-100 text-green-600'
                  }`}>
                    {question.difficulty}
                  </span>
                </div>
              </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors">
              <XCircle className="w-6 h-6 text-gray-400" />
            </button>
          </div>

          <AnimatePresence mode="wait">
            {!result ? (
              <motion.div
                key="question"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
              >
                <div className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-2xl mb-6 border border-gray-100 dark:border-gray-800">
                   <p className="text-gray-800 dark:text-gray-200 leading-relaxed font-medium">
                     {question.question}
                   </p>
                </div>

                <div className="space-y-3">
                  {question.options.map((opt: string, idx: number) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedOption(opt)}
                      className={`w-full text-left p-4 rounded-xl border-2 transition-all duration-200 group relative overflow-hidden ${
                        selectedOption === opt 
                          ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-900/20' 
                          : 'border-gray-100 dark:border-gray-800 hover:border-indigo-300 dark:hover:border-indigo-700'
                      }`}
                    >
                      <div className="flex items-center gap-3 relative z-10">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                          selectedOption === opt ? 'bg-indigo-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-500'
                        }`}>
                          {String.fromCharCode(65 + idx)}
                        </div>
                        <span className={`text-sm ${selectedOption === opt ? 'text-indigo-900 dark:text-indigo-100 font-semibold' : 'text-gray-600 dark:text-gray-400'}`}>
                          {opt}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="mt-8">
                  <button
                    onClick={handleSubmit}
                    disabled={!selectedOption || isSubmitting}
                    className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 dark:disabled:bg-gray-800 text-white rounded-2xl font-bold shadow-lg shadow-indigo-200 dark:shadow-none transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                  >
                    {isSubmitting ? 'Verifying...' : (
                      <>
                        <Send className="w-5 h-5" />
                        Submit Answer
                      </>
                    )}
                  </button>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="result"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-center py-6"
              >
                <div className="flex justify-center mb-6">
                  <div className={`p-6 rounded-full ${result.score > 0 ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'}`}>
                    {result.score > 0 ? <Trophy className="w-16 h-16" /> : <BrainCircuit className="w-16 h-16" />}
                  </div>
                </div>
                
                <h3 className="text-2xl font-black text-gray-900 dark:text-white mb-2">
                  {result.score > 0 ? 'Outstanding!' : 'Not quite right'}
                </h3>
                <p className="text-gray-500 dark:text-gray-400 mb-8">
                  {result.score > 0 
                    ? "You've mastered today's challenge and earned your daily points." 
                    : "Try again tomorrow! Review the topic in your study banks."}
                </p>

                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-2xl p-4 flex justify-around mb-8 border border-gray-100 dark:border-gray-800">
                  <div className="text-center">
                    <p className="text-[10px] uppercase font-bold text-gray-400 mb-1">Score</p>
                    <p className="text-xl font-black text-gray-900 dark:text-white">{result.score}/1</p>
                  </div>
                  <div className="text-center border-l border-gray-200 dark:border-gray-700 pl-8">
                    <p className="text-[10px] uppercase font-bold text-gray-400 mb-1">Time</p>
                    <p className="text-xl font-black text-gray-900 dark:text-white">{result.time_taken || 0}s</p>
                  </div>
                </div>

                <button
                  onClick={onClose}
                  className="w-full py-4 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-2xl font-bold transition-all active:scale-[0.98]"
                >
                  Return to Dashboard
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
