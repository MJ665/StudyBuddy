import React, { useState, useEffect } from 'react';
import { X, Code, Terminal, Brain, ListChecks, Plus, Loader2, Target } from 'lucide-react';
import ApiService from '../../services/ApiService';
import { useToast } from '../ui/Toast';

interface TestCase {
  input_data: string;
  expected_output: string;
  is_public: boolean;
  weight: number;
}

interface FormData {
  title: string;
  description: string;
  language: string;
  sample_solution: string;
  expected_approach: string;
  evaluation_criteria: string[];
  difficulty: string;
  course_id: number | string;
  is_org_public: boolean;
  test_cases: TestCase[];
}

export default function CodingQuestionModal({ user, onClose, onCreated, courses = [] }: any) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<FormData>({
    title: '',
    description: '',
    language: 'python',
    sample_solution: '',
    expected_approach: '',
    evaluation_criteria: ['Functionality', 'Logic', 'Clean Code'],
    difficulty: 'Medium',
    course_id: courses.length > 0 ? courses[0].id : '',
    is_org_public: true,
    test_cases: []
  });

  const [config, setConfig] = useState<any>(null);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const cfg = await ApiService.getSystemConfig();
        setConfig(cfg);
        if (cfg.difficulty_levels?.length > 0) {
          setFormData(prev => ({ ...prev, difficulty: cfg.difficulty_levels[0] }));
        }
      } catch (err) {
        console.error("Failed to load strategic config", err);
      }
    };
    fetchConfig();
  }, []);

  const [newCriteria, setNewCriteria] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title || !formData.sample_solution || !formData.course_id) {
      return toast.error('Title, Solution, and Course are required');
    }

    setLoading(true);
    try {
      await ApiService.createCodingQuestion({
        ...formData,
        course_id: Number(formData.course_id),
        created_by: user.id,
        test_cases: formData.test_cases.filter((tc: any) => tc.input_data && tc.expected_output)
      });
      toast.success('Coding challenge published!');
      onCreated();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const addCriteria = () => {
    if (!newCriteria.trim()) return;
    setFormData({
      ...formData,
      evaluation_criteria: [...formData.evaluation_criteria, newCriteria.trim()]
    });
    setNewCriteria('');
  };

  const removeCriteria = (index: number) => {
    setFormData({
      ...formData,
      evaluation_criteria: formData.evaluation_criteria.filter((_, i) => i !== index)
    });
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[110] flex items-center justify-center p-6 overflow-y-auto">
      <div className="bg-surface-container border border-surface-bright rounded-[2.5rem] w-full max-w-2xl shadow-2xl p-8 relative my-auto">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500 opacity-[0.05] blur-3xl -mr-20 -mt-20 pointer-events-none" />
        
        <div className="flex justify-between items-center mb-8 relative">
          <div className="flex items-center gap-3">
             <div className="w-12 h-12 bg-indigo-500/10 rounded-xl flex items-center justify-center text-indigo-400">
                <Terminal size={24} />
             </div>
             <div>
                <h3 className="text-2xl font-black text-white">Algorithmic Lab</h3>
                <p className="text-xs text-indigo-300 font-bold uppercase tracking-widest">Create Coding Assessment</p>
             </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full transition-colors text-slate-500 hover:text-white">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6 relative">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-4">
               <div>
                  <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Challenge Title</label>
                  <input 
                    type="text" 
                    value={formData.title}
                    onChange={e => setFormData({ ...formData, title: e.target.value })}
                    placeholder="e.g. Reverse a Linked List"
                    className="w-full bg-surface-dim border border-surface-bright rounded-xl p-4 text-sm text-white focus:ring-1 focus:ring-indigo-500 outline-none shadow-inner"
                  />
               </div>
               
               <div>
                  <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Problem Description</label>
                  <textarea 
                    value={formData.description}
                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Detailed requirements, constraints..."
                    className="w-full h-32 bg-surface-dim border border-surface-bright rounded-xl p-4 text-sm text-white focus:ring-1 focus:ring-indigo-500 outline-none resize-none shadow-inner"
                  />
               </div>

               <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Language</label>
                    <select 
                      value={formData.language}
                      onChange={e => setFormData({ ...formData, language: e.target.value })}
                      className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-xs text-white focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                      {config?.supported_languages?.map((lang: any) => (
                        <option key={lang.id} value={lang.id}>{lang.name}</option>
                      )) || (
                        <>
                          <option value="python">Python 3</option>
                          <option value="javascript">JavaScript (ES6)</option>
                          <option value="bash">Bash / Shell</option>
                        </>
                      )}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Difficulty</label>
                    <select 
                      value={formData.difficulty}
                      onChange={e => setFormData({ ...formData, difficulty: e.target.value })}
                      className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-xs text-white focus:ring-1 focus:ring-indigo-500 outline-none"
                    >
                      {config?.difficulty_levels?.map((d: string) => (
                        <option key={d}>{d}</option>
                      )) || (
                        <>
                          <option>Easy</option>
                          <option>Medium</option>
                          <option>Hard</option>
                        </>
                      )}
                    </select>
                  </div>
               </div>
            </div>

            <div className="space-y-4">
               <div>
                  <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2 flex justify-between items-center">
                    <span>Sample Solution</span>
                    <Code size={12} className="text-indigo-400" />
                  </label>
                  <textarea 
                    value={formData.sample_solution}
                    onChange={e => setFormData({ ...formData, sample_solution: e.target.value })}
                    placeholder="Provide a working implementation..."
                    className="w-full h-44 bg-surface-dim border border-surface-bright rounded-xl p-4 text-xs text-emerald-400 font-mono focus:ring-1 focus:ring-indigo-500 outline-none resize-none shadow-inner"
                  />
               </div>

                <div>
                   <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2 flex justify-between items-center">
                     <span>Evaluation Criteria</span>
                     <ListChecks size={12} className="text-indigo-400" />
                   </label>
                   <div className="flex gap-2 mb-2">
                     <input 
                       type="text"
                       value={newCriteria}
                       onChange={e => setNewCriteria(e.target.value)}
                       onKeyPress={e => e.key === 'Enter' && (e.preventDefault(), addCriteria())}
                       placeholder="Add criterion..."
                       className="flex-1 bg-surface-dim border border-surface-bright rounded-lg px-3 py-2 text-xs text-white outline-none"
                     />
                     <button type="button" onClick={addCriteria} className="p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors">
                       <Plus size={16} />
                     </button>
                   </div>
                   <div className="flex flex-wrap gap-2 max-h-24 overflow-y-auto">
                     {formData.evaluation_criteria.map((c, i) => (
                       <span key={i} className="px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-[9px] font-black uppercase tracking-widest rounded-md flex items-center gap-1">
                         {c}
                         <button type="button" onClick={() => removeCriteria(i)} className="hover:text-white"><X size={10} /></button>
                       </span>
                     ))}
                   </div>
                </div>

                {/* Objective Test Cases Section (NEW) */}
                <div className="p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl">
                   <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                         <Target className="text-emerald-400" size={14} />
                         <span className="text-[10px] font-black uppercase tracking-widest text-emerald-400">Objective Test Cases</span>
                      </div>
                      <button 
                        type="button" 
                        onClick={() => setFormData({
                          ...formData,
                          test_cases: [...(formData.test_cases || []), { input_data: '', expected_output: '', is_public: true, weight: 1 }]
                        })}
                        className="text-[9px] font-black text-emerald-400 hover:text-white uppercase flex items-center gap-1"
                      >
                        <Plus size={12} /> Add Case
                      </button>
                   </div>
                   <div className="space-y-3 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                      {formData.test_cases?.map((tc: any, i: number) => (
                        <div key={i} className="p-4 bg-slate-950/50 border border-white/5 rounded-2xl relative group hover:border-emerald-500/30 transition-all">
                           <button 
                             type="button" 
                             onClick={() => setFormData({
                               ...formData,
                               test_cases: formData.test_cases.filter((_: any, idx: number) => idx !== i)
                             })}
                             className="absolute -top-1 -right-1 p-1.5 bg-rose-500 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
                           >
                             <X size={12} />
                           </button>
                           <div className="grid grid-cols-2 gap-3 mb-3">
                              <div>
                                 <label className="text-[8px] font-black uppercase tracking-widest text-slate-500 mb-1 block">Input Data</label>
                                 <input 
                                   placeholder="e.g. [1,2,3]" 
                                   value={tc.input_data}
                                   onChange={e => {
                                     const newList = [...formData.test_cases];
                                     newList[i].input_data = e.target.value;
                                     setFormData({...formData, test_cases: newList});
                                   }}
                                   className="w-full bg-slate-900 border border-white/5 rounded-lg p-2 text-xs text-white focus:border-emerald-500 outline-none"
                                 />
                              </div>
                              <div>
                                 <label className="text-[8px] font-black uppercase tracking-widest text-slate-500 mb-1 block">Expected Output</label>
                                 <input 
                                   placeholder="e.g. 6" 
                                   value={tc.expected_output}
                                   onChange={e => {
                                     const newList = [...formData.test_cases];
                                     newList[i].expected_output = e.target.value;
                                     setFormData({...formData, test_cases: newList});
                                   }}
                                   className="w-full bg-slate-900 border border-white/5 rounded-lg p-2 text-xs text-white focus:border-emerald-500 outline-none"
                                 />
                              </div>
                           </div>
                           <div className="flex items-center gap-4">
                              <div className="flex-1">
                                 <label className="text-[8px] font-black uppercase tracking-widest text-slate-500 mb-1 block">Case Weight</label>
                                 <input 
                                   type="number"
                                   min="1"
                                   max="10"
                                   value={tc.weight}
                                   onChange={e => {
                                     const newList = [...formData.test_cases];
                                     newList[i].weight = parseInt(e.target.value) || 1;
                                     setFormData({...formData, test_cases: newList});
                                   }}
                                   className="w-full bg-slate-900 border border-white/5 rounded-lg p-2 text-xs text-white focus:border-emerald-500 outline-none font-black"
                                 />
                              </div>
                              <div className="flex items-center gap-2 pt-4">
                                 <input 
                                   type="checkbox"
                                   checked={tc.is_public}
                                   onChange={e => {
                                     const newList = [...formData.test_cases];
                                     newList[i].is_public = e.target.checked;
                                     setFormData({...formData, test_cases: newList});
                                   }}
                                   className="w-3.5 h-3.5 accent-emerald-500"
                                 />
                                 <span className="text-[9px] font-black uppercase tracking-widest text-slate-400">Public</span>
                              </div>
                           </div>
                        </div>
                      ))}
                      {(!formData.test_cases || formData.test_cases.length === 0) && (
                        <p className="text-[9px] text-emerald-400/50 italic text-center py-4">No objective test cases defined yet.</p>
                      )}
                   </div>
                </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
             <div>
                <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Expected Approach (AI Hint Input)</label>
                <textarea 
                  value={formData.expected_approach}
                  onChange={e => setFormData({ ...formData, expected_approach: e.target.value })}
                  placeholder="Describe the logic students should use (Time complexity, patterns...)"
                  className="w-full h-24 bg-surface-dim border border-surface-bright rounded-xl p-4 text-xs text-white focus:ring-1 focus:ring-indigo-500 outline-none resize-none shadow-inner"
                />
             </div>
              <div className="space-y-4">
                <div>
                   <label className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Target Course Alignment</label>
                   <select 
                     value={formData.course_id}
                     onChange={e => setFormData({ ...formData, course_id: e.target.value })}
                     className="w-full bg-surface-dim border border-surface-bright rounded-xl p-3 text-xs text-white focus:ring-1 focus:ring-indigo-500 outline-none"
                   >
                     <option value="">Select Course...</option>
                     {courses.map((c: any) => (
                       <option key={c.id} value={c.id}>{c.name}</option>
                     ))}
                   </select>
                </div>

                <div className="flex items-center justify-between p-4 bg-indigo-500/5 border border-indigo-500/20 rounded-2xl">
                   <div className="flex gap-2 items-center">
                     <Target className="text-indigo-400" size={14} />
                     <p className="text-[9px] text-indigo-400 font-black uppercase tracking-widest">Global Visibility</p>
                   </div>
                   <input 
                     type="checkbox" 
                     checked={formData.is_org_public} 
                     onChange={e => setFormData({ ...formData, is_org_public: e.target.checked })} 
                     className="w-4 h-4 accent-indigo-500 cursor-pointer" 
                   />
                </div>
              </div>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 text-white py-4 rounded-2xl font-black shadow-xl shadow-indigo-600/20 hover:bg-indigo-500 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" size={20} /> : <Plus size={20} />}
            Publish Algorithmic Challenge
          </button>
        </form>
      </div>
    </div>
  );
}
