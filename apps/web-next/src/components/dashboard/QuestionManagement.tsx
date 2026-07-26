import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Search, Filter, Trash2, Edit3, Database, Code, 
  ChevronRight, FilterX, BookOpen, Layers, 
  Settings, CheckCircle2, AlertTriangle, Loader2,
  MoreVertical, Download, ExternalLink, RefreshCw, Terminal
} from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';
import {ConfirmationModal} from '../ui/ConfirmationModal';

export default function QuestionManagement({ user }: { user: any }) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [banks, setBanks] = useState<any[]>([]);
  const [codingQs, setCodingQs] = useState<any[]>([]);
  const [courses, setCourses] = useState<any[]>([]);
  
  const [activeType, setActiveType] = useState<'Quiz' | 'Coding'>('Quiz');
  const [search, setSearch] = useState('');
  const [selectedCourse, setSelectedCourse] = useState<number | 'All'>('All');
  const [selectedBank, setSelectedBank] = useState<number | 'All'>('All');
  
  const [isDeleting, setIsDeleting] = useState<number | null>(null);

  // ── Inline edit (rename bank / coding question) ──
  const [editItem, setEditItem] = useState<{ id: number; type: 'Quiz' | 'Coding'; name: string; description: string } | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);

  const openEditBank = (b: any) => setEditItem({ id: b.id, type: 'Quiz', name: b.name || '', description: b.description || '' });
  const openEditCoding = (q: any) => setEditItem({ id: q.id, type: 'Coding', name: q.title || '', description: q.description || '' });

  const saveEdit = async () => {
    if (!editItem || !editItem.name.trim()) { toast('error', 'Name is required'); return; }
    setSavingEdit(true);
    try {
      if (editItem.type === 'Quiz') {
        await ApiService.updateBankMetadata(editItem.id, { name: editItem.name.trim(), description: editItem.description });
        setBanks(prev => prev.map(b => b.id === editItem.id ? { ...b, name: editItem.name.trim(), description: editItem.description } : b));
      } else {
        await ApiService.updateCodingQuestion(editItem.id, { title: editItem.name.trim(), description: editItem.description });
        setCodingQs(prev => prev.map(q => q.id === editItem.id ? { ...q, title: editItem.name.trim(), description: editItem.description } : q));
      }
      toast('success', 'Saved');
      setEditItem(null);
    } catch (err: any) {
      toast('error', err?.message || 'Failed to save');
    } finally {
      setSavingEdit(false);
    }
  };

  useEffect(() => {
    fetchResources();
  }, []);

  const fetchResources = async () => {
    setLoading(true);
    try {
      const [banksRes, codingRes, coursesRes] = await Promise.all([
        ApiService.getBanks(),
        ApiService.getCodingQuestions(),
        ApiService.getCourses(user?.group_id || 0)
      ]);
      setBanks(Array.isArray(banksRes) ? banksRes : (banksRes?.items || []));
      setCodingQs(Array.isArray(codingRes) ? codingRes : (codingRes?.items || []));
      setCourses(Array.isArray(coursesRes) ? coursesRes : (coursesRes?.items || coursesRes || []));
    } catch (err: any) {
      toast('error', 'Failed to fetch inventory');
    } finally {
      setLoading(false);
    }
  };

  const [deleteConfig, setDeleteConfig] = useState<{ id: number, type: 'Quiz' | 'Coding' } | null>(null);

  const handleDeleteBank = (id: number) => {
    setDeleteConfig({ id, type: 'Quiz' });
  };

  const handleDeleteCoding = (id: number) => {
    setDeleteConfig({ id, type: 'Coding' });
  };

  const confirmDelete = async () => {
    if (!deleteConfig) return;
    const { id, type } = deleteConfig;
    setIsDeleting(id);
    setDeleteConfig(null);
    try {
      if (type === 'Quiz') {
        await ApiService.deleteBank(id);
        setBanks(banks.filter(b => b.id !== id));
      } else {
        await ApiService.deleteCodingQuestion(id);
        setCodingQs(codingQs.filter(q => q.id !== id));
      }
      toast('success', `${type} purged from registry`);
    } catch (err: any) {
      toast('error', err.message || 'Purge failed');
    } finally {
      setIsDeleting(null);
    }
  };

  const filteredBanks = banks.filter(b => {
    const matchesSearch = b.name.toLowerCase().includes(search.toLowerCase());
    const matchesCourse = selectedCourse === 'All' || b.course_id === selectedCourse;
    return matchesSearch && matchesCourse;
  });

  const filteredCoding = codingQs.filter(q => {
    const matchesSearch = q.title.toLowerCase().includes(search.toLowerCase());
    const matchesCourse = selectedCourse === 'All' || q.course_id === selectedCourse;
    return matchesSearch && matchesCourse;
  });

  return (
    <div className="space-y-8">
      {/* Search & Filter Header */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-slate-900/50 border border-white/5 p-6 rounded-[2rem] backdrop-blur-md">
        <div className="flex items-center gap-4 bg-slate-950 border border-white/5 px-6 py-3 rounded-2xl w-full md:w-96 focus-within:border-brand-primary/50 transition-all">
          <Search size={18} className="text-slate-500" />
          <input 
            type="text" 
            placeholder="Search Registry..." 
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-transparent border-none outline-none text-sm text-white w-full font-medium"
          />
        </div>

        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex bg-slate-950 p-1 rounded-xl border border-white/5">
             <button 
               onClick={() => setActiveType('Quiz')}
               className={`px-6 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${activeType === 'Quiz' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-white'}`}
             >
               Quiz Banks
             </button>
             <button 
               onClick={() => setActiveType('Coding')}
               className={`px-6 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${activeType === 'Coding' ? 'bg-brand-primary text-slate-950' : 'text-slate-500 hover:text-white'}`}
             >
               Coding
             </button>
          </div>

          <select 
            value={selectedCourse} 
            onChange={e => setSelectedCourse(e.target.value === 'All' ? 'All' : Number(e.target.value))}
            className="bg-slate-950 border border-white/5 rounded-xl px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-slate-400 outline-none"
          >
            <option value="All">All Courses</option>
            {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>

          <button 
            onClick={fetchResources}
            className="p-2.5 bg-slate-950 border border-white/5 rounded-xl text-slate-500 hover:text-brand-primary transition-all"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Resource Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AnimatePresence mode="popLayout">
          {activeType === 'Quiz' ? (
            filteredBanks.map(bank => (
              <motion.div 
                key={bank.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-slate-900 border border-white/5 rounded-[2rem] p-8 group hover:border-indigo-500/30 transition-all flex items-center justify-between"
              >
                <div className="flex items-center gap-6">
                  <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 border border-indigo-500/20 group-hover:scale-110 transition-transform">
                    <Database size={28} />
                  </div>
                  <div>
                    <h4 className="text-lg font-black text-white mb-1">{bank.name}</h4>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1.5">
                        <BookOpen size={12} className="text-slate-500" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{courses.find(c => c.id === bank.course_id)?.name || 'General'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Layers size={12} className="text-indigo-500" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400">Quiz Bank</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all">
                  <button onClick={() => openEditBank(bank)} className="p-3 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl transition-all border border-white/5">
                    <Edit3 size={18} />
                  </button>
                  <button
                    onClick={() => handleDeleteBank(bank.id)}
                    disabled={isDeleting === bank.id}
                    className="p-3 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-xl transition-all border border-rose-500/20"
                  >
                    {isDeleting === bank.id ? <Loader2 size={18} className="animate-spin" /> : <Trash2 size={18} />}
                  </button>
                </div>
              </motion.div>
            ))
          ) : (
            filteredCoding.map(q => (
              <motion.div 
                key={q.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-slate-900 border border-white/5 rounded-[2rem] p-8 group hover:border-brand-primary/30 transition-all flex items-center justify-between"
              >
                <div className="flex items-center gap-6">
                  <div className="w-14 h-14 rounded-2xl bg-brand-primary/10 flex items-center justify-center text-brand-primary border border-brand-primary/20 group-hover:scale-110 transition-transform">
                    <Code size={28} />
                  </div>
                  <div>
                    <h4 className="text-lg font-black text-white mb-1">{q.title}</h4>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1.5">
                        <BookOpen size={12} className="text-slate-500" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{courses.find(c => c.id === q.course_id)?.name || 'General'}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Terminal size={12} className="text-brand-primary" />
                        <span className="text-[10px] font-black uppercase tracking-widest text-brand-primary">Algorithmic</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all">
                  <button onClick={() => openEditCoding(q)} className="p-3 bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white rounded-xl transition-all border border-white/5">
                    <Edit3 size={18} />
                  </button>
                  <button
                    onClick={() => handleDeleteCoding(q.id)}
                    disabled={isDeleting === q.id}
                    className="p-3 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-xl transition-all border border-rose-500/20"
                  >
                    {isDeleting === q.id ? <Loader2 size={18} className="animate-spin" /> : <Trash2 size={18} />}
                  </button>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>

        {((activeType === 'Quiz' && filteredBanks.length === 0) || (activeType === 'Coding' && filteredCoding.length === 0)) && !loading && (
          <div className="lg:col-span-2 py-20 text-center">
             <div className="w-20 h-20 bg-slate-900 border border-white/5 rounded-[2rem] flex items-center justify-center mx-auto mb-6 text-slate-600">
                <FilterX size={40} />
             </div>
             <h3 className="text-xl font-black text-white">No Sector Matches</h3>
             <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mt-2">Adjust your filters or initiate new resource protocols.</p>
          </div>
        )}

        {loading && (
          <div className="lg:col-span-2 py-20 text-center">
             <Loader2 size={40} className="text-brand-primary animate-spin mx-auto mb-6" />
             <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest">Synchronizing Registry...</p>
          </div>
        )}
      </div>

      <ConfirmationModal
        isOpen={deleteConfig !== null}
        onCancel={() => setDeleteConfig(null)}
        onConfirm={confirmDelete}
        title={deleteConfig?.type === 'Quiz' ? 'Purge Question Bank?' : 'Purge Coding Challenge?'}
        message={deleteConfig?.type === 'Quiz' 
          ? "All associated question entities and user attempt metadata will be permanently neutralized. This action is irreversible."
          : "This algorithmic challenge will be purged from the registry. Active assignments may be impacted."
        }
        confirmText="Execute Purge"
        variant="danger"
      />

      {/* ── Inline edit modal ── */}
      <AnimatePresence>
        {editItem && (
          <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={() => !savingEdit && setEditItem(null)}>
            <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} onClick={(e) => e.stopPropagation()} className="w-full max-w-lg bg-slate-900 border border-white/10 rounded-3xl p-6 shadow-2xl">
              <div className="flex items-center gap-2 text-indigo-400 mb-4"><Edit3 size={16} /><span className="font-black uppercase tracking-widest text-[10px]">Edit {editItem.type === 'Quiz' ? 'Question Bank' : 'Coding Challenge'}</span></div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">{editItem.type === 'Quiz' ? 'Bank name' : 'Title'}</label>
              <input value={editItem.name} onChange={(e) => setEditItem({ ...editItem, name: e.target.value })} className="w-full bg-slate-950 border border-white/10 rounded-xl p-3 text-sm text-white mb-4 outline-none focus:ring-1 focus:ring-indigo-500/50" />
              <label className="block text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">Description</label>
              <textarea value={editItem.description} onChange={(e) => setEditItem({ ...editItem, description: e.target.value })} rows={3} className="w-full bg-slate-950 border border-white/10 rounded-xl p-3 text-sm text-white mb-5 outline-none focus:ring-1 focus:ring-indigo-500/50" />
              <div className="flex justify-end gap-2">
                <button disabled={savingEdit} onClick={() => setEditItem(null)} className="px-4 py-2 text-slate-400 hover:text-white text-xs font-bold">Cancel</button>
                <button disabled={savingEdit} onClick={saveEdit} className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold flex items-center gap-2">
                  {savingEdit ? <Loader2 size={14} className="animate-spin" /> : 'Save'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
