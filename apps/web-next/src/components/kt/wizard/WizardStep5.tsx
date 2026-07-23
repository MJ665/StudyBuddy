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

export default function WizardStep5({ ctx }: { ctx: WizardCtx }) {
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
                <div className="h-full flex flex-col space-y-6">
                  <div className="flex justify-between items-center px-4">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                        <Terminal size={20} className="text-indigo-400" />
                      </div>
                      <h4 className="text-xl font-black text-white uppercase tracking-wider">Engineering Log</h4>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex bg-slate-900/50 p-1 rounded-2xl border border-slate-800 mr-4">
                        <button 
                          onClick={() => setEditorMode('edit')}
                          className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center gap-2 ${editorMode === 'edit' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:text-white'}`}
                        >
                          <Edit3 size={14} /> WRITE
                        </button>
                        <button 
                          onClick={() => setEditorMode('preview')}
                          className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center gap-2 ${editorMode === 'preview' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:text-white'}`}
                        >
                          <Eye size={14} /> PREVIEW
                        </button>
                      </div>
                      <button 
                        onClick={handleLocalCache}
                        className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-full text-[10px] font-black border border-slate-700 transition-all flex items-center gap-2"
                      >
                        <Save size={14} /> LOCAL CACHE
                      </button>
                      <button 
                        onClick={handleAIAssistant}
                        disabled={isAILoading}
                        className={`px-6 py-2 rounded-full text-[10px] font-black transition-all flex items-center gap-2 shadow-lg ${isAILoading ? 'bg-indigo-600/50 text-white/50 cursor-not-allowed shadow-none' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-500/20'}`}
                      >
                        {isAILoading ? (
                          <>
                            <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ANALYZING...
                          </>
                        ) : (
                          <>
                            <Sparkles size={14} /> AI ASSISTANT
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                  
                    <div className="flex-1 min-h-[500px] flex gap-6">
                      {editorMode === 'edit' ? (
                        <div className="flex-1 group relative rounded-[3rem] overflow-hidden border border-slate-800 shadow-inner">
                          <Editor
                            height="100%"
                            defaultLanguage="markdown"
                            theme="vs-dark"
                            value={formData.body_markdown}
                            onChange={(val) => setFormData({ ...formData, body_markdown: val || '' })}
                            options={{
                              minimap: { enabled: false },
                              fontSize: 16,
                              fontFamily: 'JetBrains Mono, Menlo, Monaco, Courier New, monospace',
                              padding: { top: 40, bottom: 40 },
                              lineNumbers: 'on',
                              roundedSelection: true,
                              scrollBeyondLastLine: false,
                              readOnly: false,
                              cursorStyle: 'line',
                              automaticLayout: true,
                              wordWrap: 'on',
                            }}
                          />
                          <div className="absolute bottom-10 right-10 flex gap-4 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                            <div className="bg-slate-900/90 backdrop-blur-md border border-slate-800 px-6 py-3 rounded-2xl flex items-center gap-6 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
                              <span className="flex items-center gap-2 text-indigo-400"><Terminal size={12} /> MONACO ENGINE</span>
                              <div className="w-1 h-1 rounded-full bg-slate-700" />
                              <span>{formData.body_markdown.split(/\s+/).filter(Boolean).length} Words</span>
                            </div>
                          </div>
                        </div>
                    ) : (
                      <div className="flex-1 bg-slate-950/80 border border-slate-800 rounded-[3rem] p-12 overflow-y-auto scrollbar-hide shadow-inner">
                        <article className="prose prose-invert prose-slate max-w-none 
                          prose-headings:font-black prose-headings:tracking-tighter prose-headings:text-white
                          prose-h1:text-5xl prose-h1:mb-8 prose-h1:bg-gradient-to-r prose-h1:from-white prose-h1:to-slate-500 prose-h1:bg-clip-text prose-h1:text-transparent
                          prose-h2:text-3xl prose-h2:mt-12 prose-h2:pb-4 prose-h2:border-b prose-h2:border-slate-800
                          prose-p:text-slate-300 prose-p:leading-relaxed prose-p:text-lg
                          prose-strong:text-white prose-strong:font-black
                          prose-code:text-indigo-400 prose-code:bg-indigo-500/10 prose-code:px-2 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none
                          prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline
                          prose-img:rounded-[2rem] prose-img:border prose-img:border-slate-800
                          prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-800 prose-pre:rounded-[2rem] prose-pre:p-8
                          prose-li:text-slate-300 prose-li:marker:text-indigo-500
                          prose-blockquote:border-l-4 prose-blockquote:border-indigo-500 prose-blockquote:bg-indigo-500/5 prose-blockquote:px-8 prose-blockquote:py-1 prose-blockquote:rounded-r-2xl
                        ">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {formData.body_markdown || '*No content yet. Start writing in the editor to see it here.*'}
                          </ReactMarkdown>
                        </article>
                      </div>
                    )}
                  </div>
                </div>
</>
  );
}
