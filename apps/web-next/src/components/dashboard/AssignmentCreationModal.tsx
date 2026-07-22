import React, { useState, useEffect } from 'react';
import { X, Calendar, Lock, Target, AlertCircle, Loader2, Plus, Brain, Terminal } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

export default function AssignmentCreationModal({ user, onClose, onCreated }: any) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [banks, setBanks] = useState<any[]>([]);
  const [codingQuestions, setCodingQuestions] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [targetTypes, setTargetTypes] = useState<{id: string, name: string}[]>([]);

  const [formData, setFormData] = useState({
    title: '',
    assignment_type: 'quiz', // 'quiz' or 'coding'
    target_type: 'group', // 'org', 'dept', 'vertical', 'batch', 'group'
    target_id: '',
    bank_id: '',
    coding_question_id: '',
    due_date: '',
    max_attempts: 1,
    passing_score: 70,
    is_compulsory: true,
    lock_after_due: true,
    grace_period_hours: 24,
  });

  const [targets, setTargets] = useState<{
    orgs: any[],
    depts: any[],
    verticals: any[],
    batches: any[],
    groups: any[]
  }>({ orgs: [], depts: [], verticals: [], batches: [], groups: [] });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    fetchTargets(formData.target_type);
  }, [formData.target_type]);

  const fetchTargets = async (type: string) => {
    try {
      let data: any[] = [];
      if (type === 'org') data = await ApiService.getOrgs();
      else if (type === 'dept') data = await ApiService.getDepartments();
      else if (type === 'vertical') data = await ApiService.getVerticals();
      else if (type === 'batch') data = await ApiService.getBatches();
      else data = await ApiService.getGroups();

      setTargets(prev => ({ ...prev, [`${type}s`]: data }));
      if (data.length > 0) {
        setFormData(prev => ({ ...prev, target_id: data[0].id }));
      } else {
        setFormData(prev => ({ ...prev, target_id: '' }));
      }
    } catch (err) {
      toast.error(`Failed to fetch ${type} targets`);
    }
  };

  const fetchData = async () => {
    try {
      const [banksRes, codingRes] = await Promise.all([
        ApiService.getBanks(),
        ApiService.getCodingQuestions()
      ]);
      
      const banksArr: any[] = Array.isArray(banksRes) ? banksRes : (banksRes?.items || banksRes?.banks || []);
      setBanks(banksArr);

      const codingArr: any[] = Array.isArray(codingRes) ? codingRes : (codingRes?.items || []);
      setCodingQuestions(codingArr);
      
      if (banksArr.length > 0) setFormData(prev => ({ ...prev, bank_id: banksArr[0].id }));
      if (codingArr.length > 0) setFormData(prev => ({ ...prev, coding_question_id: codingArr[0].id }));
      
      // Dynamically load target levels
      try {
        const levels = await ApiService.getTargetLevels();
        setTargetTypes(levels);
      } catch (err) {
        // Fallback for registry data
        setTargetTypes([
          { id: 'group', name: 'Group (Specific)' },
          { id: 'batch', name: 'Batch (All Groups in Batch)' },
          { id: 'vertical', name: 'Vertical (All Batches)' },
          { id: 'dept', name: 'Department (All Verticals)' },
          { id: 'org', name: 'Organization (Global)' }
        ]);
      }
    } catch (err: any) {
      toast.error('Failed to load assignment dependencies');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title) return toast.error('Assignment title is required');
    if (!formData.target_id) return toast.error('Target is required');
    
    if (formData.assignment_type === 'quiz' && !formData.bank_id) return toast.error('Assessment Bank is required');
    if (formData.assignment_type === 'coding' && !formData.coding_question_id) return toast.error('Coding Question is required');
    
    setLoading(true);
    try {
      await ApiService.createAssignment({
        title: formData.title,
        assignment_type: formData.assignment_type,
        target_type: formData.target_type,
        target_id: Number(formData.target_id),
        bank_id: formData.assignment_type === 'quiz' ? Number(formData.bank_id) : null,
        coding_question_id: formData.assignment_type === 'coding' ? Number(formData.coding_question_id) : null,
        passing_score_percent: Number(formData.passing_score),
        max_attempts: Number(formData.max_attempts),
        due_date: formData.due_date ? new Date(formData.due_date).toISOString() : null,
        lock_after_due: formData.lock_after_due,
        grace_period_hours: formData.grace_period_hours,
        is_compulsory: formData.is_compulsory,
      });
      toast.success('Assignment mandated successfully!');
      onCreated();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getTargetOptions = () => {
    switch (formData.target_type) {
      case 'org': return targets.orgs;
      case 'dept': return targets.depts;
      case 'vertical': return targets.verticals;
      case 'batch': return targets.batches;
      default: return targets.groups;
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[110] flex items-center justify-center p-6">
      <div className="bg-surface-container border border-surface-bright rounded-[2.5rem] w-full max-w-xl shadow-2xl p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-brand-primary opacity-[0.05] blur-3xl -mr-20 -mt-20 pointer-events-none" />
        
        <div className="flex justify-between items-center mb-8 relative">
          <div>
            <h3 className="text-2xl font-black text-white">Direct Mandate</h3>
            <p className="text-xs text-on-surface-variant font-bold uppercase tracking-widest">Enforce Learning Compliance</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full transition-colors text-slate-500 hover:text-white">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6 relative">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Assignment Title</label>
              <input 
                type="text" 
                placeholder="e.g. Q2 Performance Review"
                value={formData.title}
                onChange={e => setFormData({ ...formData, title: e.target.value })}
                className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-sm text-white focus:ring-1 focus:ring-brand-primary outline-none"
              />
            </div>
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Type</label>
              <div className="flex p-1 bg-surface-dim border border-surface-bright rounded-xl">
                <button 
                  type="button"
                  onClick={() => setFormData({ ...formData, assignment_type: 'quiz' })}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-[10px] font-black transition-all ${formData.assignment_type === 'quiz' ? 'bg-slate-900 text-brand-primary shadow-lg' : 'text-slate-500'}`}
                >
                  <Brain size={14} /> QUIZ
                </button>
                <button 
                  type="button"
                  onClick={() => setFormData({ ...formData, assignment_type: 'coding' })}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-[10px] font-black transition-all ${formData.assignment_type === 'coding' ? 'bg-slate-900 text-indigo-400 shadow-lg' : 'text-slate-500'}`}
                >
                  <Terminal size={14} /> CODING
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Target Level</label>
              <select 
                value={formData.target_type}
                onChange={e => {
                  const type = e.target.value;
                  setFormData({ 
                    ...formData, 
                    target_type: type
                  });
                }}
                className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-sm text-white focus:ring-1 focus:ring-brand-primary outline-none font-bold"
              >
                {targetTypes.length === 0 ? (
                  <option value="group">Group (Specific)</option>
                ) : (
                  targetTypes.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))
                )}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Select Target</label>
              <select 
                value={formData.target_id}
                onChange={e => setFormData({ ...formData, target_id: e.target.value })}
                className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-sm text-white focus:ring-1 focus:ring-brand-primary outline-none"
              >
                {getTargetOptions().map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">
              {formData.assignment_type === 'quiz' ? 'Assessment Bank' : 'Coding Challenge'}
            </label>
            <select 
              value={formData.assignment_type === 'quiz' ? formData.bank_id : formData.coding_question_id}
              onChange={e => setFormData({ 
                ...formData, 
                [formData.assignment_type === 'quiz' ? 'bank_id' : 'coding_question_id']: e.target.value 
              })}
              className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-sm text-white focus:ring-1 focus:ring-brand-primary outline-none"
            >
              {formData.assignment_type === 'quiz' 
                ? banks.map(b => <option key={b.id} value={b.id}>{b.name}</option>)
                : codingQuestions.map(q => <option key={q.id} value={q.id}>{q.title}</option>)
              }
            </select>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Deadline</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                <input 
                  type="datetime-local" 
                  value={formData.due_date}
                  onChange={e => setFormData({ ...formData, due_date: e.target.value })}
                  className="w-full bg-surface-dim border border-surface-bright rounded-xl pl-10 pr-4 py-3 text-xs text-white outline-none"
                />
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Attempt Limit</label>
              <div className="relative">
                <Target className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                <input 
                  type="number" 
                  min="1"
                  value={formData.max_attempts}
                  onChange={e => setFormData({ ...formData, max_attempts: parseInt(e.target.value) || 1 })}
                  className="w-full bg-surface-dim border border-surface-bright rounded-xl pl-10 pr-4 py-3 text-xs text-white outline-none"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Passing Score (%)</label>
              <input 
                type="number" 
                max="100"
                min="0"
                value={formData.passing_score}
                onChange={e => setFormData({ ...formData, passing_score: parseInt(e.target.value) || 0 })}
                className="w-full bg-surface-dim border border-surface-bright rounded-xl px-4 py-3 text-xs text-white outline-none"
              />
            </div>
            <div className="flex flex-col justify-center gap-2">
               <div className="flex items-center gap-2">
                 <input 
                   type="checkbox" 
                   id="is_compulsory"
                   checked={formData.is_compulsory}
                   onChange={e => setFormData({ ...formData, is_compulsory: e.target.checked })}
                   className="w-4 h-4 accent-brand-primary"
                 />
                 <label htmlFor="is_compulsory" className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Mandatory</label>
               </div>
               <div className="flex items-center gap-2">
                 <input 
                   type="checkbox" 
                   id="lock_after_due"
                   checked={formData.lock_after_due}
                   onChange={e => setFormData({ ...formData, lock_after_due: e.target.checked })}
                   className="w-4 h-4 accent-brand-primary"
                 />
                 <label htmlFor="lock_after_due" className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Lock Post-Deadline</label>
               </div>
               {formData.lock_after_due && (
                 <div className="mt-2">
                   <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-1">Grace Period (Hours)</label>
                   <input 
                     type="number" 
                     min="0"
                     value={formData.grace_period_hours}
                     onChange={e => setFormData({ ...formData, grace_period_hours: parseInt(e.target.value) || 0 })}
                     className="w-full bg-surface-dim border border-surface-bright rounded-xl px-3 py-2 text-xs text-white outline-none"
                   />
                 </div>
               )}
            </div>
          </div>

          <div className="p-4 bg-brand-primary/10 border border-brand-primary/20 rounded-2xl flex gap-3">
            <AlertCircle className="text-brand-primary shrink-0" size={18} />
            <p className="text-[10px] text-brand-primary/80 font-bold leading-relaxed">
              Mandates at higher levels (Org/Vertical) will cascade to all constituent members. High-density tracking will be active.
            </p>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-brand-primary text-surface-dim py-4 rounded-2xl font-black shadow-xl shadow-brand-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : <Plus size={20} />}
            Initialize Mandate
          </button>
        </form>
      </div>
    </div>
  );
}
