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

export default function WizardStep0({ ctx }: { ctx: WizardCtx }) {
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
                     <h3 className="text-4xl font-black text-white tracking-tighter">Define the Identity</h3>
                     <p className="text-slate-500 font-medium text-lg">Every document is a structured contract for organizational intelligence.</p>
                  </div>

                  <div className="space-y-3">
                    <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Document Title</label>
                    <input 
                      type="text" 
                      placeholder="e.g. Migration to Temporal IO for Ingestion"
                      className="w-full bg-slate-950/50 border border-slate-800 rounded-[2rem] p-8 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-3xl font-black tracking-tight text-white placeholder:text-slate-800 transition-all"
                      value={formData.title}
                      onChange={e => setFormData({...formData, title: e.target.value})}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between ml-1">
                        <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500">Target Project</label>
                        <button 
                          onClick={() => setIsNewProject(!isNewProject)}
                          className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                        >
                          {isNewProject ? <X size={12} /> : <Plus size={12} />}
                          {isNewProject ? 'Cancel' : 'Add New'}
                        </button>
                      </div>
                      {isNewProject ? (
                        <input 
                          type="text"
                          placeholder="Project Name..."
                          className="w-full bg-slate-950/50 border border-indigo-500/30 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white"
                          value={newProjectName}
                          onChange={e => setNewProjectName(e.target.value)}
                        />
                      ) : (
                        <select 
                          className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-slate-300 appearance-none cursor-pointer"
                          value={formData.project_id}
                          onChange={e => setFormData({...formData, project_id: e.target.value})}
                        >
                          {loadingInitial ? <option>Loading projects...</option> : projects.map(p => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>
                      )}
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Document Type</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-slate-300 appearance-none cursor-pointer"
                        value={formData.doc_type}
                        onChange={e => setFormData({...formData, doc_type: e.target.value})}
                      >
                        {registries.docTypes.map(dt => (
                          <option key={dt.id} value={dt.id}>{dt.name}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Client Name</label>
                      <input 
                        type="text" 
                        placeholder="e.g. FinBank Ltd"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.client_name}
                        onChange={e => setFormData({...formData, client_name: e.target.value})}
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Department</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Backend Platform"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.department}
                        onChange={e => setFormData({...formData, department: e.target.value})}
                      />
                    </div>
                  </div>
                </div>
</>
  );
}
