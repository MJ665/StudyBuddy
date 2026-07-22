


import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Send, AlertCircle, Loader2, CheckCircle2, MessageSquare } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

interface InterventionModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetUserIds: number[];
  targetUserNames: string[];
}

export default function InterventionModal({ isOpen, onClose, targetUserIds, targetUserNames }: InterventionModalProps) {
  const { toast } = useToast();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSend = async () => {
    if (!message.trim()) return;
    setSending(true);
    try {
      await ApiService.notifyIntervention({
        user_ids: targetUserIds,
        message: message.trim()
      });
      setSent(true);
      toast('success', 'Pedagogical Intervention Dispatched');
      setTimeout(() => {
        onClose();
        setSent(false);
        setMessage('');
      }, 2000);
    } catch (err: any) {
      toast('error', `Intervention failed: ${err.message}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[200] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="bg-slate-900 border border-slate-800 rounded-[2.5rem] p-8 w-full max-w-lg shadow-2xl relative"
          >
            <div className="flex justify-between items-center mb-8">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-2xl text-amber-400">
                  <AlertCircle size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">Direct Intervention</h3>
                  <p className="text-xs text-slate-500">Dispatch targeted pedagogical guidance</p>
                </div>
              </div>
              <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
                <X size={24} />
              </button>
            </div>

            <div className="mb-6">
              <label className="block text-[10px] font-black uppercase text-slate-500 tracking-widest mb-3">Recipients</label>
              <div className="flex flex-wrap gap-2">
                {targetUserNames.map((name, i) => (
                  <span key={i} className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-xs font-bold text-slate-300">
                    {name}
                  </span>
                ))}
              </div>
            </div>

            <div className="mb-8">
              <label className="block text-[10px] font-black uppercase text-slate-500 tracking-widest mb-3">Intervention Message</label>
              <div className="relative">
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g. Your Knowledge Velocity has dipped in the last 72 hours. Let's focus on the 'Database Indexing' module this afternoon..."
                  className="w-full h-40 bg-slate-950 border border-slate-800 rounded-2xl p-4 text-white text-sm outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/50 transition-all resize-none placeholder:text-slate-600"
                />
                <div className="absolute bottom-4 right-4 pointer-events-none opacity-20">
                  <MessageSquare size={40} className="text-amber-500" />
                </div>
              </div>
            </div>

            <div className="flex gap-4">
              <button
                onClick={onClose}
                className="flex-1 py-4 text-xs font-black uppercase tracking-widest text-slate-500 hover:text-white transition-colors"
              >
                Cancel Protocol
              </button>
              <button
                onClick={handleSend}
                disabled={sending || !message.trim() || sent}
                className={`flex-[2] py-4 rounded-2xl font-black uppercase tracking-widest text-xs flex items-center justify-center gap-2 transition-all shadow-lg ${
                  sent 
                    ? 'bg-emerald-600 text-white shadow-emerald-600/20' 
                    : 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-600/20 disabled:opacity-50'
                }`}
              >
                {sending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : sent ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <Send size={16} />
                )}
                {sending ? 'Dispatching...' : sent ? 'Intervention Dispatched' : 'Initialize Intervention'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
