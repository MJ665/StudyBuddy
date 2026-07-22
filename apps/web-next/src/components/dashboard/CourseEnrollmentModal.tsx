import React, { useState, useEffect } from 'react';
import { X, Book, Target, AlertCircle, Loader2, BookmarkPlus } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

export default function CourseEnrollmentModal({ onClose, onEnrolled }: any) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [courses, setCourses] = useState<any[]>([]);
  const [tree, setTree] = useState<any[]>([]);
  
  const [targetType, setTargetType] = useState<'Group' | 'Vertical'>('Group');
  const [targetId, setTargetId] = useState('');
  const [courseId, setCourseId] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [coursesRes, treeRes] = await Promise.all([
        ApiService.getCourses(0), // Admin context
        ApiService.getOrgTree()
      ]);
      setCourses(coursesRes);
      setTree(treeRes);
      
      if (coursesRes.length > 0) setCourseId(coursesRes[0].id);
    } catch (err: any) {
      toast.error('Failed to load strategic dependencies');
    }
  };

  const getAllGroups = (nodes: any[]): any[] => {
    let groups: any[] = [];
    nodes.forEach(node => {
      if (node.groups) groups.push(...node.groups.map((g: any) => ({ ...g, context: node.name })));
      const children = node.departments || node.verticals || node.batches;
      if (children) groups = [...groups, ...getAllGroups(children)];
    });
    return groups;
  };

  const getAllVerticals = (nodes: any[]): any[] => {
    let verts: any[] = [];
    nodes.forEach(node => {
      if (node.departments) {
        node.departments.forEach((d: any) => {
           if (d.verticals) verts.push(...d.verticals.map((v: any) => ({ ...v, context: d.name })));
        });
      }
      const children = node.departments || node.verticals || node.batches;
      if (children) verts = [...verts, ...getAllVerticals(children)];
    });
    return verts;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetId || !courseId) return toast.error('Selection required');
    
    setLoading(true);
    try {
      if (targetType === 'Group') {
        await ApiService.subscribeGroup(Number(targetId), Number(courseId));
      } else {
        await ApiService.subscribeVertical(Number(targetId), Number(courseId));
      }
      toast.success('Course mandated successfully!');
      onEnrolled();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const targets = targetType === 'Group' ? getAllGroups(tree) : getAllVerticals(tree);

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[110] flex items-center justify-center p-6">
      <div className="bg-surface-container border border-surface-bright rounded-[2.5rem] w-full max-w-lg shadow-2xl p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500 opacity-[0.05] blur-3xl -mr-20 -mt-20 pointer-events-none" />
        
        <div className="flex justify-between items-center mb-8 relative">
          <div>
            <h3 className="text-2xl font-black text-white">Course Enrollment</h3>
            <p className="text-xs text-on-surface-variant font-bold uppercase tracking-widest">Global Curriculum Deployment</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full transition-colors text-slate-500 hover:text-white">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6 relative">
          <div className="grid grid-cols-2 gap-4">
            <button 
              type="button"
              onClick={() => { setTargetType('Group'); setTargetId(''); }}
              className={`py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${targetType === 'Group' ? 'bg-brand-primary text-slate-950' : 'bg-white/5 text-slate-400'}`}
            >
              Target Group
            </button>
            <button 
              type="button"
              onClick={() => { setTargetType('Vertical'); setTargetId(''); }}
              className={`py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${targetType === 'Vertical' ? 'bg-indigo-500 text-white' : 'bg-white/5 text-slate-400'}`}
            >
              Target Vertical
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Subject Node</label>
              <select 
                value={targetId}
                onChange={e => setTargetId(e.target.value)}
                className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-sm text-white focus:ring-1 focus:ring-brand-primary outline-none"
              >
                <option value="">Select {targetType}...</option>
                {targets.map(t => <option key={t.id} value={t.id}>{t.context ? `${t.context} / ` : ''}{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Pedagogical Course</label>
              <select 
                value={courseId}
                onChange={e => setCourseId(e.target.value)}
                className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-sm text-white focus:ring-1 focus:ring-brand-primary outline-none"
              >
                {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>

          <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl flex gap-3">
            <AlertCircle className="text-indigo-400 shrink-0" size={18} />
            <p className="text-[10px] text-indigo-400/80 font-bold leading-relaxed">
              Enrolling these nodes will grant immediate synchronization access to all constituent members and mentors.
            </p>
          </div>

          <button 
            type="submit"
            disabled={loading || !targetId || !courseId}
            className="w-full bg-brand-primary text-surface-dim py-4 rounded-2xl font-black shadow-xl shadow-brand-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : <BookmarkPlus size={20} />}
            Execute Strategic Enrollment
          </button>
        </form>
      </div>
    </div>
  );
}
