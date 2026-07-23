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

export default function WizardStep1({ ctx }: { ctx: WizardCtx }) {
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
                     <h3 className="text-4xl font-black text-white tracking-tighter">People & Time</h3>
                     <p className="text-slate-500 font-medium text-lg">Knowledge is temporal. Defining when it was created and who verified it is crucial.</p>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="col-span-2 p-6 bg-indigo-500/5 border border-indigo-500/10 rounded-[2rem] flex items-center justify-between mb-2">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 font-black">
                          {user?.full_name?.charAt(0) || user?.name?.charAt(0) || 'A'}
                        </div>
                        <div>
                          <p className="text-white font-black">{user?.full_name || user?.name || 'Document Author'}</p>
                          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">You are the primary owner</p>
                        </div>
                      </div>
                      <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400 bg-indigo-500/10 px-4 py-2 rounded-full border border-indigo-500/20">
                        Owner
                      </span>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Assigned Mentor (Reviewer)</label>
                      <select 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-slate-300 appearance-none cursor-pointer"
                        value={formData.mentor_id || ''}
                        onChange={e => setFormData({...formData, mentor_id: e.target.value ? parseInt(e.target.value) : null})}
                      >
                        <option value="">Select a Mentor...</option>
                        {mentors.map(m => (
                          <option key={m.id} value={m.id}>{m.full_name || m.name || m.email}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Co-Authors</label>
                      <div className="relative">
                        <div className="relative">
                          <input 
                            type="text" 
                            placeholder="Search colleagues by name or email..."
                            className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                            value={coAuthorSearch}
                            onChange={e => setCoAuthorSearch(e.target.value)}
                          />
                          {isSearchingCoAuthors && (
                            <div className="absolute right-6 top-1/2 -translate-y-1/2">
                              <Sparkles className="animate-spin text-indigo-400" size={20} />
                            </div>
                          )}
                        </div>

                        {coAuthorResults.length > 0 && (
                          <div className="absolute z-10 w-full mt-2 bg-slate-900 border border-slate-800 rounded-[1.5rem] shadow-2xl overflow-hidden">
                            {coAuthorResults.map(user => (
                              <button
                                key={user.user_id}
                                onClick={() => {
                                  if (!formData.co_author_ids.includes(user.user_id)) {
                                    setFormData({
                                      ...formData,
                                      co_author_ids: [...formData.co_author_ids, user.user_id],
                                      co_author_names: [...formData.co_author_names, user.name],
                                      co_author_emails: [...formData.co_author_emails, user.email]
                                    });
                                  }
                                  setCoAuthorSearch('');
                                  setCoAuthorResults([]);
                                }}
                                className="w-full p-6 text-left hover:bg-indigo-500/10 border-b border-slate-800 last:border-0 flex justify-between items-center transition-colors group"
                              >
                                <div>
                                  <p className="text-white font-black">{user.name}</p>
                                  <p className="text-slate-500 text-xs font-bold">{user.email}</p>
                                </div>
                                {user.group_name && (
                                  <span className="text-[10px] font-black uppercase tracking-widest text-indigo-400 bg-indigo-500/10 px-3 py-1 rounded-full group-hover:bg-indigo-500 group-hover:text-white transition-all">
                                    {user.group_name}
                                  </span>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                        {coAuthorSearch && !isSearchingCoAuthors && coAuthorResults.length === 0 && (
                          <div className="mt-4 p-4 bg-rose-500/5 border border-rose-500/10 rounded-2xl">
                            <p className="text-rose-400 text-xs font-bold">No users found in your organization. Co-authors must be registered members.</p>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex flex-wrap gap-3 mt-6">
                        {formData.co_author_ids.map((id, i) => (
                          <div key={id} className="bg-indigo-500/10 border border-indigo-500/20 px-6 py-3 rounded-2xl flex items-center gap-3 text-indigo-400 font-black text-sm group hover:border-indigo-500 transition-all">
                            <div className="flex flex-col">
                              <span>{formData.co_author_names[i]}</span>
                              <span className="text-[10px] opacity-60">{formData.co_author_emails[i]}</span>
                            </div>
                            <button 
                              onClick={() => {
                                setFormData({
                                  ...formData,
                                  co_author_ids: formData.co_author_ids.filter((_, idx) => idx !== i),
                                  co_author_names: formData.co_author_names.filter((_, idx) => idx !== i),
                                  co_author_emails: formData.co_author_emails.filter((_, idx) => idx !== i)
                                });
                              }}
                              className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-slate-500 hover:bg-rose-500 hover:text-white transition-all"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        ))}
                        {formData.co_author_ids.length === 0 && !coAuthorSearch && (
                          <p className="text-slate-600 text-xs font-bold italic ml-2">No co-authors added yet. They will be notified via email.</p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Start Date</label>
                      <input 
                        type="date" 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white cursor-pointer"
                        value={formData.date_range_start}
                        onChange={e => setFormData({...formData, date_range_start: e.target.value})}
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">End Date</label>
                      <input 
                        type="date" 
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white cursor-pointer"
                        value={formData.date_range_end}
                        onChange={e => setFormData({...formData, date_range_end: e.target.value})}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-10">
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Sprint</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Sprint 14-17"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.sprint}
                        onChange={e => setFormData({...formData, sprint: e.target.value})}
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="text-xs font-black uppercase tracking-[0.25em] text-slate-500 ml-1">Milestone</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Phase 2 Go-Live"
                        className="w-full bg-slate-950/50 border border-slate-800 rounded-[1.5rem] p-6 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 font-bold text-lg text-white placeholder:text-slate-800"
                        value={formData.milestone}
                        onChange={e => setFormData({...formData, milestone: e.target.value})}
                      />
                    </div>
                  </div>
                </div>
</>
  );
}
