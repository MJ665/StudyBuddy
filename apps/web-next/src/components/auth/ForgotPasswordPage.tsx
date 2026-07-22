import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Mail, ChevronLeft, ArrowRight, Loader2, ShieldCheck } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

export default function ForgotPasswordPage({ onBack, onSuccess }: { onBack: () => void, onSuccess: (email: string, groupId: number) => void }) {
  const { toast } = useToast();
  const [email, setEmail] = useState('');
  const [groupId, setGroupId] = useState<number | ''>('');
  const [groups, setGroups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchingGroups, setFetchingGroups] = useState(true);

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        const res = await ApiService.getGroups();
        setGroups(res || []);
      } catch (err) {
        toast('error', 'Failed to fetch organizational nodes.');
      } finally {
        setFetchingGroups(false);
      }
    };
    fetchGroups();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !groupId) return;

    setLoading(true);
    try {
      await ApiService.forgotPassword(email, Number(groupId));
      toast('success', 'Recovery OTP dispatched to your registered email.');
      onSuccess(email, Number(groupId));
    } catch (err: any) {
      toast('error', err.message || 'Recovery failed. Verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 relative overflow-hidden">
      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-600/5 rounded-full blur-3xl -mr-64 -mt-64" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-brand-primary/5 rounded-full blur-3xl -ml-64 -mb-64" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md bg-slate-900 border border-white/5 rounded-[2.5rem] p-10 shadow-2xl relative z-10"
      >
        <button 
          onClick={onBack}
          className="flex items-center gap-2 text-slate-500 hover:text-white transition-all text-xs font-black uppercase tracking-widest mb-10 group"
        >
          <ChevronLeft size={16} className="group-hover:-translate-x-1 transition-transform" /> Back to Terminal
        </button>

        <div className="mb-10">
          <div className="w-16 h-16 bg-brand-primary/10 rounded-2xl flex items-center justify-center text-brand-primary mb-6">
            <ShieldCheck size={32} />
          </div>
          <h2 className="text-3xl font-black text-white mb-2">Account Recovery</h2>
          <p className="text-sm text-slate-500 font-bold leading-relaxed">
            Initialize password reset protocol. We will transmit a secure OTP to your registered corporate address.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2 ml-1">Corporate Node</label>
            <select 
              required
              value={groupId}
              onChange={e => setGroupId(Number(e.target.value))}
              disabled={fetchingGroups}
              className="w-full bg-slate-950 border border-white/5 rounded-2xl p-5 text-white font-bold outline-none focus:ring-2 focus:ring-brand-primary/30 transition-all appearance-none disabled:opacity-50"
            >
              <option value="">Select Organization...</option>
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-2 ml-1">Email Identifier</label>
            <div className="relative">
              <Mail className="absolute left-5 top-1/2 -translate-y-1/2 text-slate-600" size={18} />
              <input 
                type="email" 
                required
                placeholder="satoshi@bitcoin.org"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full bg-slate-950 border border-white/5 rounded-2xl p-5 pl-14 text-white font-bold outline-none focus:ring-2 focus:ring-brand-primary/30 transition-all"
              />
            </div>
          </div>

          <button 
            type="submit"
            disabled={loading || fetchingGroups}
            className="w-full bg-brand-primary hover:bg-brand-primary/90 text-slate-950 py-5 rounded-[2rem] font-black uppercase tracking-widest shadow-xl shadow-brand-primary/20 transition-all flex items-center justify-center gap-3 disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" /> : <>Initialize Recovery <ArrowRight size={18} /></>}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
