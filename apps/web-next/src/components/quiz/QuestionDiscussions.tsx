/**
 * QuestionDiscussions.tsx
 * High-fidelity discussion interface for peer-to-peer learning.
 * Features threaded replies, mentor pinning, and real-time synthesis.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  MessageSquare, Send, X, CornerDownRight, ThumbsUp,
  Flag, Pin, ShieldCheck, Loader2, Sparkles, User, Clock
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

interface Discussion {
  id: number;
  user_id: number;
  user_name: string;
  content: string;
  upvotes: number;
  is_pinned: boolean;
  created_at: string;
  replies: Discussion[];
}

interface QuestionDiscussionsProps {
  questionId: number;
  onClose: () => void;
}

export default function QuestionDiscussions({ questionId, onClose }: QuestionDiscussionsProps) {
  const { toast } = useToast();
  const [discussions, setDiscussions] = useState<Discussion[]>([]);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [replyTo, setReplyTo] = useState<number | null>(null);

  const fetchDiscussions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await ApiService.getDiscussions(questionId);
      setDiscussions(data);
    } catch (err: any) {
      toast('error', 'Failed to synchronize discussions');
    } finally {
      setLoading(false);
    }
  }, [questionId, toast]);

  useEffect(() => {
    fetchDiscussions();
  }, [fetchDiscussions]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comment.trim()) return;

    setSubmitting(true);
    try {
      await ApiService.addDiscussion(questionId, comment, replyTo || undefined);
      setComment('');
      setReplyTo(null);
      fetchDiscussions();
      toast('success', 'Logic contribution published');
    } catch (err: any) {
      toast('error', 'Publication failure');
    } finally {
      setSubmitting(false);
    }
  };

  const CommentCard = ({ d, isReply = false }: { d: Discussion, isReply?: boolean, key?: any }) => (
    <div className={`group relative ${isReply ? 'ml-8 mt-4' : 'mt-6'}`}>
      {isReply && (
        <div className="absolute -left-6 top-4 w-4 h-4 border-l-2 border-b-2 border-slate-700 rounded-bl-lg" />
      )}

      <div className={`p-5 rounded-2xl border transition-all duration-300 ${d.is_pinned
          ? 'bg-indigo-500/10 border-indigo-500/30 shadow-[0_0_20px_rgba(99,102,241,0.1)]'
          : 'bg-slate-900/50 border-white/5 hover:border-white/10'
        }`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-white/5 flex items-center justify-center text-xs font-black text-slate-400">
              {d.user_name.charAt(0)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-black text-white">{d.user_name}</span>
                {d.is_pinned && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-indigo-500/20 text-indigo-400 text-[10px] font-black uppercase tracking-widest rounded-full">
                    <Pin size={10} /> Explanation
                  </span>
                )}
              </div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                {new Date(d.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all">
            <button className="p-1.5 hover:bg-white/5 text-slate-500 hover:text-white rounded-lg transition-all">
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => {
                setReplyTo(d.id);
                document.getElementById('discussion-input')?.focus();
              }}
              className="p-1.5 hover:bg-white/5 text-slate-500 hover:text-white rounded-lg transition-all"
            >
              <CornerDownRight size={14} />
            </button>
            <button className="p-1.5 hover:bg-white/5 text-slate-500 hover:text-rose-400 rounded-lg transition-all">
              <Flag size={14} />
            </button>
          </div>
        </div>

        <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
          {d.content}
        </p>
      </div>

      {d.replies?.map(reply => (
        <CommentCard key={reply.id} d={reply} isReply />
      ))}
    </div>
  );

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-slate-950/80 backdrop-blur-md"
        onClick={onClose}
      />

      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9, y: 20 }}
        className="relative w-full max-w-2xl h-[80vh] bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-[0_0_100px_rgba(0,0,0,0.5)] flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="p-8 border-b border-white/5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-indigo-500/20 border border-indigo-500/30 rounded-2xl flex items-center justify-center">
              <MessageSquare className="text-indigo-400" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-tight">Peer Discussions</h2>
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">Collaborative Reasoning & Synthesis</p>
            </div>
          </div>
          <button onClick={onClose} className="p-3 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl transition-all border border-white/5">
            <X size={20} />
          </button>
        </div>

        {/* Discussions List */}
        <div className="flex-1 overflow-y-auto p-8 scrollbar-thin scrollbar-thumb-white/10">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <Loader2 className="text-indigo-500 animate-spin" size={32} />
              <p className="text-xs font-black text-slate-500 uppercase tracking-widest animate-pulse">Synchronizing Neural Links...</p>
            </div>
          ) : discussions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-6">
              <div className="w-20 h-20 bg-slate-800/50 rounded-[2rem] flex items-center justify-center">
                <Sparkles size={40} className="text-slate-600" />
              </div>
              <div>
                <h3 className="text-lg font-black text-white mb-2 uppercase tracking-tight">The Floor is Yours</h3>
                <p className="text-slate-500 text-sm max-w-xs mx-auto leading-relaxed">No logic explained yet. Be the first to start the pedagogical synthesis for this question.</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4 pb-8">
              {discussions.map(d => (
                <CommentCard key={d.id} d={d} />
              ))}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-8 bg-slate-900/50 border-t border-white/5 shrink-0">
          {replyTo && (
            <div className="flex items-center justify-between bg-indigo-500/10 border border-indigo-500/20 px-4 py-2 rounded-xl mb-4">
              <div className="flex items-center gap-2">
                <CornerDownRight size={14} className="text-indigo-400" />
                <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Replying to thread</span>
              </div>
              <button onClick={() => setReplyTo(null)} className="text-indigo-400 hover:text-white transition-all">
                <X size={14} />
              </button>
            </div>
          )}
          <form onSubmit={handleSubmit} className="relative">
            <textarea
              id="discussion-input"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Explain your reasoning or ask a question..."
              className="w-full bg-slate-800 border border-white/5 rounded-2xl p-5 pr-20 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all resize-none min-h-[100px]"
            />
            <button
              type="submit"
              disabled={submitting || !comment.trim()}
              className="absolute bottom-4 right-4 p-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-xl shadow-indigo-500/20 transition-all disabled:opacity-50 disabled:grayscale"
            >
              {submitting ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
            </button>
          </form>
          <p className="mt-4 text-[9px] font-bold text-slate-600 uppercase tracking-widest text-center">
            Helpful, high-fidelity logic explanations improve your Consistency Index.
          </p>
        </div>
      </motion.div>
    </div>
  );
}
