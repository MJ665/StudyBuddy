import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Map, X, Sparkles, Loader2, CheckCircle2, Clock, BookOpen, Target, ChevronRight } from 'lucide-react';
import ApiService, { SystemConfig } from '../../services/ApiService';
import { useToast } from '../ui/Toast';

interface PathPhase {
  week_range: string;
  title: string;
  topics: string[];
  activities: string[];
  milestone: string;
}

interface LearningPath {
  goal: string;
  estimated_weeks: number;
  phases: PathPhase[];
  resources: string[];
  success_metric: string;
}

interface AILearningPathProps {
  onClose: () => void;
}

export default function AILearningPath({ onClose }: AILearningPathProps) {
  const { toast } = useToast();
  const [view, setView] = useState<'form' | 'result' | 'saved'>('form');
  const [goal, setGoal] = useState('');
  const [level, setLevel] = useState('Intermediate');
  const [hours, setHours] = useState(5);
  const [loading, setLoading] = useState(false);
  const [path, setPath] = useState<LearningPath | null>(null);
  const [savedPaths, setSavedPaths] = useState<any[]>([]);
  const [expandedPhase, setExpandedPhase] = useState<number | null>(0);
  const [learnerLevels, setLearnerLevels] = useState<string[]>(['Beginner', 'Intermediate', 'Advanced']);

  useEffect(() => {
    ApiService.getSystemConfig().then((config: SystemConfig) => {
      if (config.learner_levels) setLearnerLevels(config.learner_levels);
    }).catch(err => console.error("Failed to load learner levels", err));
  }, []);

  const fetchSaved = async () => {
    try {
      const res = await ApiService.getSavedLearningPaths();
      // Handle potential envelope for list
      const paths = Array.isArray(res) ? res : (res.data || []);
      setSavedPaths(paths);
      if (paths.length > 0) {
        setView('saved');
      } else {
        toast('info', 'No saved paths found yet. Generate your first one!');
      }
    } catch (err: any) {
      console.error(err);
      toast('error', 'Failed to fetch saved paths');
    }
  };

  const handleGenerate = async () => {
    if (!goal.trim()) {
      toast('error', 'Please enter your learning goal');
      return;
    }
    setLoading(true);
    setPath(null);
    try {
      const res = await ApiService.getAILearningPath({
        goal: goal.trim(),
        current_level: level,
        available_hours_per_week: hours
      });
      
      // Handle potential AI response envelope
      if (res.ai_generated === false) {
        toast('error', res.fallback_reason || 'AI generation failed.');
        return;
      }
      
      const actualPath = res.data ? res.data : res;
      setPath(actualPath);
      setView('result');
      toast('success', 'New roadmap generated and saved!');
    } catch (err: any) {
      toast('error', `Failed to generate path: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const selectSaved = (p: any) => {
    setPath(p.roadmap);
    setView('result');
  };

  const levelColors = {
    Beginner: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    Intermediate: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    Advanced: 'bg-rose-500/10 text-rose-400 border-rose-500/20'
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-500/20 rounded-2xl flex items-center justify-center">
              <Map size={20} className="text-purple-400" />
            </div>
            <div>
              <h2 className="text-white font-bold text-lg">AI Learning Path</h2>
              <p className="text-slate-500 text-xs">Personalised week-by-week curriculum via Gemini</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {view === 'form' && (
              <button 
                onClick={fetchSaved}
                className="text-xs font-bold text-purple-400 hover:text-purple-300 bg-purple-500/10 px-3 py-1.5 rounded-xl border border-purple-500/20"
              >
                Saved Paths
              </button>
            )}
            <button onClick={onClose} className="text-slate-500 hover:text-white p-1 transition-colors">
              <X size={22} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Saved Paths List */}
          {view === 'saved' && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-black uppercase tracking-widest text-slate-500">Your Saved Roadmaps</p>
                <button onClick={() => setView('form')} className="text-xs font-bold text-purple-400">Create New</button>
              </div>
              <div className="space-y-3">
                {savedPaths.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => selectSaved(p)}
                    className="w-full p-4 bg-slate-800/40 border border-slate-700/50 rounded-2xl hover:bg-slate-800 transition-all text-left group"
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-white font-bold text-sm group-hover:text-purple-400 transition-colors">{p.topic}</p>
                      <ChevronRight size={14} className="text-slate-600" />
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-tighter">
                      Created {new Date(p.created_at).toLocaleDateString()}
                    </p>
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Input Form */}
          {view === 'form' && (
            <>
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 block">Your Learning Goal *</label>
                <textarea
                  value={goal}
                  onChange={e => setGoal(e.target.value)}
                  placeholder="e.g. Master React and TypeScript for full-stack development..."
                  rows={3}
                  className="w-full bg-slate-800 border border-slate-700 rounded-2xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:border-purple-500 transition-colors text-sm resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 block">Current Level</label>
                  <div className="space-y-1.5">
                    {learnerLevels.map(l => (
                      <button
                        key={l}
                        onClick={() => setLevel(l)}
                        className={`w-full py-2 px-3 rounded-xl text-xs font-bold border text-left transition-all ${
                          level === l
                            ? (levelColors as any)[l] || 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                            : 'bg-slate-800 border-slate-700 text-slate-500 hover:border-slate-600'
                        }`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 block">Hours / Week</label>
                  <input
                    type="number"
                    value={hours}
                    onChange={e => setHours(Math.max(1, Math.min(40, parseInt(e.target.value) || 5)))}
                    min={1}
                    max={40}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-2xl font-black text-center focus:outline-none focus:border-purple-500 transition-colors"
                  />
                  <p className="text-xs text-slate-600 text-center mt-1">hours per week</p>
                </div>
              </div>

              <button
                onClick={handleGenerate}
                disabled={loading || !goal.trim()}
                className="w-full py-3.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-2xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-purple-500/20"
              >
                {loading ? (
                  <><Loader2 size={18} className="animate-spin" /> Crafting your path...</>
                ) : (
                  <><Sparkles size={18} /> Generate My Learning Path</>
                )}
              </button>
            </>
          )}

          {/* Result */}
          <AnimatePresence>
            {view === 'result' && path && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
                {/* Summary */}
                <div className="bg-purple-950/60 border border-purple-500/30 rounded-2xl p-5">
                  <div className="flex justify-between items-start mb-1">
                    <h3 className="text-white font-bold text-lg leading-tight">{path.goal}</h3>
                    <button onClick={() => setView('form')} className="text-[10px] uppercase font-bold text-purple-400 shrink-0 border border-purple-500/20 px-2 py-0.5 rounded">New</button>
                  </div>
                  <div className="flex gap-4 mt-3">
                    <div className="flex items-center gap-1.5 text-xs text-slate-400">
                      <Clock size={12} className="text-purple-400" />
                      {path.estimated_weeks} weeks
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-slate-400">
                      <Target size={12} className="text-purple-400" />
                      {path.phases?.length || 0} phases
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 mt-3 italic leading-relaxed">
                    <span className="text-purple-400 font-bold not-italic">Success: </span>
                    {path.success_metric}
                  </p>
                </div>

                {/* Phases */}
                <div className="space-y-2">
                  <p className="text-xs font-black uppercase tracking-widest text-slate-500">Curriculum Phases</p>
                  {(path.phases || []).map((phase, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.06 }}
                      className="bg-slate-800/50 border border-slate-700/50 rounded-2xl overflow-hidden"
                    >
                      <button
                        onClick={() => setExpandedPhase(expandedPhase === idx ? null : idx)}
                        className="w-full flex items-center justify-between p-4 text-left"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-7 h-7 bg-purple-500/20 rounded-lg flex items-center justify-center shrink-0">
                            <span className="text-xs font-black text-purple-400">{idx + 1}</span>
                          </div>
                          <div>
                            <p className="text-white font-bold text-sm">{phase.title}</p>
                            <p className="text-slate-500 text-xs">{phase.week_range}</p>
                          </div>
                        </div>
                        <ChevronRight
                          size={16}
                          className={`text-slate-500 transition-transform ${expandedPhase === idx ? 'rotate-90' : ''}`}
                        />
                      </button>

                      <AnimatePresence>
                        {expandedPhase === idx && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="px-4 pb-4 space-y-3"
                          >
                            <div>
                              <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1.5">Topics</p>
                              <div className="flex flex-wrap gap-1.5">
                                {phase.topics.map((t, ti) => (
                                  <span key={ti} className="px-2 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-lg text-xs font-medium">{t}</span>
                                ))}
                              </div>
                            </div>
                            <div>
                              <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1.5">Activities</p>
                              <ul className="space-y-1">
                                {phase.activities.map((a, ai) => (
                                  <li key={ai} className="flex items-start gap-2 text-xs text-slate-400">
                                    <CheckCircle2 size={10} className="text-emerald-400 mt-0.5 shrink-0" />
                                    {a}
                                  </li>
                                ))}
                              </ul>
                            </div>
                            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-3">
                              <p className="text-[10px] font-black uppercase tracking-widest text-emerald-400 mb-1">Milestone</p>
                              <p className="text-xs text-slate-300">{phase.milestone}</p>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  ))}
                </div>

                {/* Resources */}
                {path.resources && path.resources.length > 0 && (
                  <div>
                    <p className="text-xs font-black uppercase tracking-widest text-slate-500 mb-2">Recommended Resources</p>
                    <ul className="space-y-1.5">
                      {path.resources.map((r, ri) => (
                        <li key={ri} className="flex items-center gap-2 text-sm text-slate-400">
                          <BookOpen size={12} className="text-purple-400 shrink-0" />
                          {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {view === 'form' && (
          <div className="p-4 border-t border-slate-800 shrink-0">
            <button onClick={onClose} className="w-full py-3 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-2xl font-bold text-sm transition-all border border-slate-700">
              Close
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
}
