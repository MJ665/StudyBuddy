import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  MessageSquare, Users, TrendingUp, Search, Filter,
  MessageCircle, ThumbsUp, ChevronRight, Clock, Hash,
  Plus, ArrowLeft, MoreHorizontal, Pin
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';
import QuestionDiscussions from '../quiz/QuestionDiscussions';

export default function DiscussionForum({ user, onViewProfile, onBack }: { user: any, onViewProfile: (slug: string) => void, onBack: () => void }) {
  const { toast } = useToast();
  const [threads, setThreads] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedBankId, setSelectedBankId] = useState<number | null>(null);
  const [banks, setBanks] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeQuestionId, setActiveQuestionId] = useState<number | null>(null);

  useEffect(() => {
    fetchBanks();
  }, []);

  useEffect(() => {
    fetchThreads();
  }, [page, selectedBankId]);

  const fetchBanks = async () => {
    try {
      const res = await ApiService.getBanks();
      setBanks(Array.isArray(res) ? res : res.items || []);
    } catch (err) {
      console.error("Failed to fetch banks", err);
    }
  };

  const fetchThreads = async () => {
    setLoading(true);
    try {
      const res = await ApiService.getGlobalDiscussions(selectedBankId || undefined, page);
      setThreads(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      toast('error', 'Failed to synchronize community terminal');
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async (id: number, direction: 'up' | 'down') => {
    try {
      const res = await ApiService.request(`/interaction/discussions/${id}/vote?direction=${direction}`, { method: 'POST' });
      setThreads(prev => prev.map(t => t.id === id ? { ...t, upvotes: res.upvotes } : t));
    } catch (err: any) {
      toast('error', 'Transmission failed');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <div className="max-w-7xl mx-auto px-8 py-10">

        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-indigo-500/10 rounded-xl text-indigo-400">
                <MessageSquare size={20} />
              </div>
              <h1 className="text-3xl font-black text-white">Community Terminal</h1>
            </div>
            <p className="text-slate-500 text-sm font-bold uppercase tracking-widest">Global Peer-to-Peer Knowledge Exchange</p>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative">
              <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="bg-slate-900 border border-white/5 rounded-2xl pl-12 pr-6 py-3 text-sm text-white focus:border-indigo-500 outline-none transition-all w-full md:w-64"
              />
            </div>
            <button
              onClick={onBack}
              className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white rounded-2xl font-black text-xs uppercase tracking-widest transition-all border border-white/10 flex items-center gap-2"
            >
              <ArrowLeft size={16} /> Exit
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">

          {/* Sidebar Filters */}
          <aside className="lg:col-span-1 space-y-8">
            <div className="p-6 bg-slate-900/60 rounded-[2rem] border border-white/5">
              <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2">
                <Filter size={14} /> Knowledge Domains
              </h3>
              <div className="space-y-2">
                <button
                  onClick={() => setSelectedBankId(null)}
                  className={`w-full text-left px-4 py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-between ${!selectedBankId ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' : 'text-slate-400 hover:bg-white/5'}`}
                >
                  All Domains
                </button>
                {banks.slice(0, 10).map(bank => (
                  <button
                    key={bank.id}
                    onClick={() => setSelectedBankId(bank.id)}
                    className={`w-full text-left px-4 py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-between ${selectedBankId === bank.id ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' : 'text-slate-400 hover:bg-white/5'}`}
                  >
                    <span className="truncate">{bank.name}</span>
                    {selectedBankId === bank.id && <ChevronRight size={14} />}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-6 bg-gradient-to-br from-indigo-600 to-purple-700 rounded-[2rem] shadow-xl shadow-indigo-600/20">
              <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center text-white mb-4">
                <TrendingUp size={24} />
              </div>
              <h3 className="text-lg font-black text-white mb-2">Contribution Rank</h3>
              <p className="text-white/70 text-xs leading-relaxed mb-6">Your insights help the community grow. Active contributors earn the 'Core Oracle' badge.</p>
              <div className="h-1.5 bg-white/20 rounded-full overflow-hidden">
                <div className="h-full bg-white w-2/3" />
              </div>
              <p className="text-[10px] text-white/50 font-black uppercase tracking-widest mt-3">Level 4 — 2.4k Karma</p>
            </div>
          </aside>

          {/* Main Feed */}
          <main className="lg:col-span-3">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-32 space-y-4">
                <div className="animate-spin w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full" />
                <p className="text-slate-500 font-black text-[10px] uppercase tracking-widest animate-pulse">Syncing Threads...</p>
              </div>
            ) : threads.length === 0 ? (
              <div className="py-32 text-center bg-slate-900/40 rounded-[3rem] border border-white/5 border-dashed">
                <MessageCircle size={48} className="text-slate-800 mx-auto mb-6" />
                <h3 className="text-xl font-black text-white mb-2">Silence in the Domain</h3>
                <p className="text-slate-500 text-sm mb-8">No discussions found for this sector. Be the first to initiate contact.</p>
                <button className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-black text-sm transition-all shadow-lg shadow-indigo-600/20">
                  NEW BROADCAST
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                {threads.filter(t => t.content.toLowerCase().includes(searchQuery.toLowerCase())).map((thread, i) => (
                  <motion.div
                    key={thread.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="group bg-slate-900/60 hover:bg-slate-900/80 border border-white/5 hover:border-white/10 rounded-[2.5rem] p-8 transition-all relative"
                  >
                    {thread.is_pinned && (
                      <div className="absolute top-8 right-8 text-indigo-400">
                        <Pin size={18} />
                      </div>
                    )}

                    <div className="flex items-start gap-6">
                      {/* Vote Controls */}
                      <div className="flex flex-col items-center gap-2 pt-1">
                        <button
                          onClick={() => handleVote(thread.id, 'up')}
                          className="p-2 text-slate-600 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-xl transition-all"
                        >
                          <ThumbsUp size={18} />
                        </button>
                        <span className="text-sm font-black text-white">{thread.upvotes}</span>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-3">
                          <div
                            onClick={() => thread.user_slug && onViewProfile(thread.user_slug)}
                            className="w-8 h-8 bg-indigo-500/20 border border-indigo-500/30 rounded-lg flex items-center justify-center text-indigo-400 text-xs font-black cursor-pointer hover:bg-indigo-500/30 transition-all"
                          >
                            {thread.user_name.charAt(0)}
                          </div>
                          <div>
                            <p
                              onClick={() => thread.user_slug && onViewProfile(thread.user_slug)}
                              className="text-sm font-black text-white cursor-pointer hover:text-indigo-400 transition-colors"
                            >
                              {thread.user_name}
                            </p>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest flex items-center gap-2">
                              <Clock size={10} /> {new Date(thread.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>

                        <div className="bg-slate-950/40 rounded-2xl p-6 mb-6 border border-white/5">
                          <p className="text-slate-300 leading-relaxed">{thread.content}</p>
                        </div>

                        <div className="flex flex-wrap items-center gap-4">
                          <div className="flex items-center gap-2 px-3 py-1.5 bg-white/5 rounded-xl border border-white/5">
                            <Hash size={12} className="text-slate-500" />
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{thread.bank_name}</span>
                          </div>

                          <div className="h-4 w-px bg-white/5" />

                          <button
                            onClick={() => setActiveQuestionId(thread.question_id)}
                            className="flex items-center gap-2 text-[10px] font-black text-indigo-400 uppercase tracking-widest hover:text-indigo-300 transition-colors"
                          >
                            <MessageCircle size={14} /> {thread.reply_count} Replies
                          </button>

                          <div className="ml-auto flex items-center gap-2 text-[10px] font-black text-slate-600 uppercase tracking-widest italic truncate max-w-[200px]">
                            Context: {thread.question_text}
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}

                {/* Pagination */}
                {total > 20 && (
                  <div className="flex items-center justify-center gap-4 pt-8">
                    <button
                      disabled={page === 1}
                      onClick={() => setPage(p => p - 1)}
                      className="p-3 bg-white/5 hover:bg-white/10 text-white rounded-xl border border-white/5 disabled:opacity-30 transition-all"
                    >
                      <ArrowLeft size={18} />
                    </button>
                    <span className="text-sm font-black text-slate-500">Domain {page} of {Math.ceil(total / 20)}</span>
                    <button
                      disabled={page * 20 >= total}
                      onClick={() => setPage(p => p + 1)}
                      className="p-3 bg-white/5 hover:bg-white/10 text-white rounded-xl border border-white/5 disabled:opacity-30 transition-all"
                    >
                      <ChevronRight size={18} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Discussion Detail Modal */}
      <AnimatePresence>
        {activeQuestionId && (
          <QuestionDiscussions
            questionId={activeQuestionId}
            onClose={() => setActiveQuestionId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
