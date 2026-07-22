import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Library, 
  Search, 
  Filter, 
  BrainCircuit, 
  Clock, 
  ChevronRight,
  Shield,
  Users,
  Star,
  Zap,
  Loader2,
  Tag
} from 'lucide-react';
import ApiService from '../../services/ApiService';

interface Bank {
  id: number;
  name: string;
  category: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  question_count: number;
  total_attempts: number;
  avg_score: number;
  visibility_scope: string;
}

interface QuestionLibraryProps {
  user: any;
  onStartQuiz: (bank: any, maxQuestions: number) => void;
  onBack: () => void;
}

export default function QuestionLibrary({ user, onStartQuiz, onBack }: QuestionLibraryProps) {
  const [banks, setBanks] = useState<Bank[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  useEffect(() => {
    fetchBanks();
  }, []);

  const fetchBanks = async () => {
    try {
      const data = await ApiService.getBanks();
      // Handle paginated response or legacy array response
      if (data && data.items) {
        setBanks(data.items);
      } else {
        setBanks(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error("Failed to fetch banks", err);
    } finally {
      setLoading(false);
    }
  };

  const categories = ['All', ...Array.from(new Set(banks.map(b => b.category || 'Uncategorized')))];

  const filteredBanks = banks.filter(b => {
    const matchesSearch = b.name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || b.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="min-h-screen bg-slate-950 p-8 font-plus-jakarta">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-12 gap-6">
          <div>
            <h1 className="text-4xl font-black text-white mb-2 tracking-tight flex items-center gap-4">
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-emerald-400">
                <Library size={32} />
              </div>
              Knowledge Library
            </h1>
            <p className="text-slate-500 font-bold uppercase tracking-[0.2em] text-[10px]">Global Repository of Academic & Technical Directives</p>
          </div>

          <div className="flex items-center gap-4">
             <div className="relative group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-emerald-400 transition-colors" size={18} />
                <input 
                  type="text" 
                  placeholder="Query knowledge base..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="bg-slate-900/50 border border-white/5 rounded-2xl py-3 pl-12 pr-6 text-sm text-white focus:ring-2 focus:ring-emerald-500/20 w-full md:w-64 transition-all"
                />
             </div>
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex items-center gap-3 overflow-x-auto pb-6 custom-scrollbar mb-8">
           {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-6 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest whitespace-nowrap transition-all ${
                  selectedCategory === cat 
                    ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-600/20' 
                    : 'bg-slate-900/50 text-slate-500 border border-white/5 hover:text-slate-300'
                }`}
              >
                {cat}
              </button>
           ))}
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-32 space-y-4">
            <Loader2 className="animate-spin text-emerald-500" size={48} />
            <p className="text-slate-500 font-black uppercase tracking-widest text-xs">Indexing Global Knowledge...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredBanks.map((bank, idx) => (
              <motion.div
                key={bank.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="group bg-slate-900/40 backdrop-blur-xl border border-white/5 rounded-[2.5rem] p-8 hover:bg-slate-900/60 transition-all hover:scale-[1.02] cursor-pointer"
                onClick={() => onStartQuiz(bank, 50)}
              >
                <div className="flex justify-between items-start mb-6">
                   <div className="p-3 bg-slate-950 rounded-2xl text-emerald-400">
                      <BrainCircuit size={24} />
                   </div>
                   <div className={`px-3 py-1 rounded-full text-[8px] font-black uppercase tracking-[0.2em] ${
                      bank.difficulty === 'advanced' ? 'bg-rose-500/10 text-rose-400' :
                      bank.difficulty === 'intermediate' ? 'bg-amber-500/10 text-amber-400' :
                      'bg-emerald-500/10 text-emerald-400'
                   }`}>
                      {bank.difficulty || 'Intermediate'}
                   </div>
                </div>

                <h3 className="text-xl font-black text-white mb-2 group-hover:text-emerald-400 transition-colors line-clamp-1">{bank.name}</h3>
                <div className="flex items-center gap-4 mb-6">
                   <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                      <Tag size={12} className="text-indigo-400" /> {bank.category || 'General'}
                   </div>
                   <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                      <Clock size={12} className="text-amber-400" /> 20m
                   </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-8">
                   <div className="bg-slate-950/50 p-4 rounded-2xl border border-white/5">
                      <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1 text-center">Questions</p>
                      <p className="text-lg font-black text-white text-center">{bank.question_count || 0}</p>
                   </div>
                   <div className="bg-slate-950/50 p-4 rounded-2xl border border-white/5">
                      <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1 text-center">Attempts</p>
                      <p className="text-lg font-black text-white text-center">{bank.total_attempts || 0}</p>
                   </div>
                </div>

                <div className="flex items-center justify-between">
                   <div className="flex items-center gap-2">
                      <Users size={14} className="text-slate-600" />
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{bank.visibility_scope || 'Public Domain'}</span>
                   </div>
                   <div className="flex items-center gap-1 text-emerald-400 font-black text-xs">
                      START <ChevronRight size={16} className="group-hover:translate-x-1 transition-transform" />
                   </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
        
        {!loading && filteredBanks.length === 0 && (
           <div className="py-32 text-center bg-slate-900/20 rounded-[3rem] border border-dashed border-white/5">
              <Library size={64} className="mx-auto text-slate-800 mb-6" />
              <h3 className="text-2xl font-black text-white mb-2">Knowledge Void</h3>
              <p className="text-slate-500 font-medium">No directives found matching your current filter set.</p>
           </div>
        )}
      </div>
    </div>
  );
}
