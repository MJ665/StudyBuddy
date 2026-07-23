'use client';
/* Extracted verbatim from KTCreationWizard.tsx (5b decomposition). State
   and handlers arrive via the ctx object assembled in the wizard shell. */
/* eslint-disable @typescript-eslint/no-unused-vars */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ChevronRight, ChevronLeft, Save, Sparkles, 
  AlertCircle, CheckCircle2, Type, Hash, 
  Terminal, Globe, Shield, Calendar, X, Plus, Eye, Edit3
} from 'lucide-react';
import ApiService from '../../../services/ApiService';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'react-hot-toast';
import Editor from '@monaco-editor/react';

interface WizardProps {
  user: any;
  projectId?: string;
  onClose: () => void;
  onComplete?: (data: any) => void;
}

const STEPS = [
  { id: 'identity', title: 'Identity', icon: Type },
  { id: 'people_time', title: 'People & Time', icon: Calendar },
  { id: 'intelligence', title: 'Intelligence', icon: Sparkles },
  { id: 'context', title: 'Context', icon: Globe },
  { id: 'learnings', title: 'Learnings', icon: Sparkles },
  { id: 'body', title: 'Body', icon: Terminal }
];

import type { WizardCtx } from './types';

export default function WizardStep2({ ctx }: { ctx: WizardCtx }) {
  const { currentStep, setCurrentStep, projects, mentors, loadingInitial, tagInput,
    setTagInput, coAuthorInput, setCoAuthorInput, isNewProject, setIsNewProject,
    newProjectName, setNewProjectName, editorMode, setEditorMode, isSaving,
    registries, formData, setFormData, coAuthorSearch, setCoAuthorSearch,
    coAuthorResults, setCoAuthorResults, isSearchingCoAuthors, isAILoading, next, back,
    addListItem, removeListItem, calculateCompleteness, handleFinalize,
    handleSaveDraft, handleLocalCache, handleAIAssistant,
    user, projectId, onClose, onComplete } = ctx;
  return (
<>
                <div className="space-y-12 max-w-3xl mx-auto">
                   <div className="space-y-4 text-center mb-12">
                     <h3 className="text-4xl font-black text-white tracking-tighter">Technicals & Intelligence</h3>
                     <p className="text-slate-500 font-medium text-lg">Tag the specific stack and access levels to ensure safe, precise retrieval.</p>
                  </div>
                  
                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Technical Stack</label>
                    <div className="flex gap-4">
                      <input 
                        type="text"
                        placeholder="Add technology (e.g. Neo4j, Redis, FastAPI)..."
                        className="flex-1 bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={tagInput}
                        onChange={e => setTagInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && addListItem('tech_stack', tagInput, setTagInput)}
                      />
                      <button 
                        onClick={() => addListItem('tech_stack', tagInput, setTagInput)}
                        className="px-10 bg-indigo-600 hover:bg-indigo-500 text-white rounded-[1.5rem] font-black tracking-tight transition-all shadow-lg shadow-indigo-500/20"
                      >
                        ADD
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-3 p-8 bg-slate-950/30 border border-slate-800 rounded-[2rem] min-h-[140px] items-start content-start">
                      {formData.tech_stack.length === 0 ? (
                        <div className="m-auto text-center space-y-2 opacity-30">
                          <Terminal size={32} className="mx-auto text-slate-500" />
                          <p className="text-slate-500 text-xs font-black uppercase tracking-widest">No technologies added</p>
                        </div>
                      ) : (
                        formData.tech_stack.map(tag => (
                          <motion.span 
                            layout
                            key={tag}
                            className="px-6 py-3 bg-slate-800 border border-slate-700 rounded-2xl text-sm font-black text-slate-300 flex items-center gap-3 group hover:border-indigo-500/50 transition-all shadow-sm"
                          >
                            {tag}
                            <button onClick={() => removeListItem('tech_stack', tag)} className="text-slate-500 hover:text-rose-400 transition-colors">
                              <X size={16} />
                            </button>
                          </motion.span>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-8">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Complexity</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.25rem] p-5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-slate-300 appearance-none cursor-pointer"
                        value={formData.complexity}
                        onChange={e => setFormData({...formData, complexity: e.target.value})}
                      >
                        {registries.complexities.map(c => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Access Level</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.25rem] p-5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-slate-300 appearance-none cursor-pointer"
                        value={formData.access_level}
                        onChange={e => setFormData({...formData, access_level: e.target.value})}
                      >
                        {registries.accessLevels.map(a => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Sensitivity</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.25rem] p-5 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-slate-300 appearance-none cursor-pointer"
                        value={formData.sensitivity}
                        onChange={e => setFormData({...formData, sensitivity: e.target.value})}
                      >
                        {registries.sensitivities.map(s => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-8 bg-indigo-500/5 border border-indigo-500/10 rounded-[2rem]">
                    <div>
                      <h4 className="text-lg font-black text-white">Evergreen Knowledge?</h4>
                      <p className="text-slate-500 text-sm font-medium mt-1">Is this information timeless (Architecture) or time-bound (Sprint Notes)?</p>
                    </div>
                    <button 
                      onClick={() => setFormData({...formData, is_evergreen: !formData.is_evergreen})}
                      className={`w-16 h-8 rounded-full transition-all relative ${formData.is_evergreen ? 'bg-indigo-600' : 'bg-slate-800'}`}
                    >
                      <div className={`absolute top-1 w-6 h-6 rounded-full bg-white transition-all ${formData.is_evergreen ? 'left-9' : 'left-1'}`} />
                    </button>
                  </div>
                </div>
</>
  );
}
