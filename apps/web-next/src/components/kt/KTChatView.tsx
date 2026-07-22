'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  MessageSquare, Send, ArrowLeft, Loader2, Bot, User, 
  ShieldCheck, AlertCircle, FileText, Trash2, Cpu, ThumbsUp, ThumbsDown
} from 'lucide-react';
import ApiService from '@/services/ApiService';
import { useKTNavStore } from '@/stores/ktNavStore';
import { useKTGateStore } from '@/stores/ktGateStore';
import KTGate from './KTGate';
import { toast } from 'react-hot-toast';

export default function KTChatView() {
  const { selectedProject, setView } = useKTNavStore();
  const [messages, setMessages] = useState<any[]>([]);
  const [query, setQuery] = useState('');
  const [typing, setTyping] = useState(false);

  const gateStore = useKTGateStore();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [internalAuth, setInternalAuth] = useState(false);
  const [startingSession, setStartingSession] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, typing]);

  const hasStartedRef = useRef(false);

  useEffect(() => {
    // Check internal JWT auth
    const token = localStorage.getItem('study_token');
    if (token) {
      if (!internalAuth) {
        setInternalAuth(true);
      }
      if (gateStore.authMode !== 'jwt') {
        gateStore.setAuthMode('jwt');
      }
      // Auto-start session for the project
      if (selectedProject && !sessionId && !startingSession && !hasStartedRef.current) {
        hasStartedRef.current = true;
        setStartingSession(true);
        ApiService.startKTChatSession([selectedProject.id])
          .then(res => setSessionId(res.session_id))
          .catch(err => {
            console.error('Failed to start session:', err);
            hasStartedRef.current = false;
          })
          .finally(() => setStartingSession(false));
      }
    }
  }, [selectedProject, sessionId, startingSession, internalAuth, gateStore.authMode]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const actualSessionId = sessionId || gateStore.sessionId;
    if (!query.trim() || !actualSessionId) return;

    const userQuery = query.trim();
    setQuery('');
    setMessages(prev => [...prev, { role: 'user', content: userQuery }]);
    setTyping(true);

    try {
      const res = await ApiService.askKTQuestion(
        actualSessionId, 
        userQuery, 
        internalAuth ? undefined : gateStore.rawKey
      );
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.content || res.answer,
          sources: res.sources || [],
          confidence: res.confidence_score !== undefined ? res.confidence_score : 90
        }
      ]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I failed to scan the graph indexes. Verify your key connection limits.',
          isError: true
        }
      ]);
    } finally {
      setTyping(false);
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
    toast.success('Chat history cleared locally');
  };

  const handleFeedback = (idx: number, isHelpful: boolean) => {
    setMessages(prev => prev.map((msg, i) => {
      if (i === idx) {
        return { ...msg, feedback: isHelpful };
      }
      return msg;
    }));
    toast.success(isHelpful ? 'Positive feedback recorded' : 'Feedback logged for improvement');
  };

  if (!selectedProject) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-sm">
          <MessageSquare className="mx-auto text-slate-700 mb-4" size={40} />
          <h3 className="text-lg font-bold text-slate-400">No Project Scope Selected</h3>
          <p className="text-xs text-slate-500 mt-2 mb-6">
            Please select a technical project registry container from the projects panel first to ask scoped graph questions.
          </p>
          <button
            onClick={() => setView('projects')}
            className="bg-indigo-600 hover:bg-indigo-500 text-white py-3 px-6 rounded-2xl font-bold text-xs uppercase tracking-widest transition-all"
          >
            Select Project
          </button>
        </div>
      </div>
    );
  }

  // Render unlock gate if unverified and not internal auth
  if (!internalAuth && gateStore.gateState !== 'verified') {
    return (
      <KTGate
        projectId={selectedProject.id}
        projectName={selectedProject.name}
        onUnlock={(key, sid) => {
          setSessionId(sid);
        }}
        onCancel={() => setView('projects')}
      />
    );
  }

  const actualSessionId = sessionId || gateStore.sessionId;
  
  if (startingSession || !actualSessionId) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <Loader2 className="animate-spin text-indigo-500" size={48} />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 relative overflow-hidden z-10 w-full">
      {/* Header Info Panel */}
      <div className="px-8 py-5 border-b border-slate-900 bg-slate-950/60 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 border border-indigo-500/20">
            <Cpu size={20} />
          </div>
          <div>
            <h3 className="font-bold text-white text-sm">{selectedProject.name} AI Assistant</h3>
            <div className="flex items-center gap-1.5 mt-0.5">
              <ShieldCheck size={12} className="text-emerald-400 animate-pulse" />
              <span className="text-[9px] font-black uppercase text-emerald-400 tracking-wider">Gateway Decrypted</span>
            </div>
          </div>
        </div>

        <button
          onClick={handleClearHistory}
          className="text-slate-500 hover:text-slate-300 p-2.5 rounded-xl bg-slate-900 border border-slate-850 transition-colors"
          title="Clear local chat"
        >
          <Trash2 size={16} />
        </button>
      </div>

      {/* Messages viewport */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar"
      >
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto text-slate-500 py-12">
            <Bot size={48} className="text-indigo-500 mb-6 opacity-30 animate-pulse" />
            <h4 className="text-base font-bold text-slate-400">Ask the Knowledge Graph</h4>
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              Query codebase architecture design, deployment strategies, and sprint backlogs locked in database registries.
            </p>
          </div>
        )}

        {messages.map((msg, i) => {
          const isUser = msg.role === 'user';
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex items-start gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center border shrink-0 text-xs font-bold ${
                isUser 
                  ? 'bg-indigo-600 border-indigo-500 text-white' 
                  : 'bg-slate-900 border-slate-800 text-indigo-400'
              }`}>
                {isUser ? <User size={14} /> : <Bot size={14} />}
              </div>

              <div className={`max-w-[75%] p-6 rounded-[2rem] space-y-4 ${
                isUser 
                  ? 'bg-indigo-600 text-white rounded-tr-none shadow-lg shadow-indigo-500/10' 
                  : msg.isError
                    ? 'bg-rose-950/20 border border-rose-500/20 text-rose-300 rounded-tl-none'
                    : 'bg-slate-900/60 border border-slate-850 text-slate-200 rounded-tl-none'
              }`}>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                {/* Sources badge mapping */}
                {!isUser && msg.sources && msg.sources.length > 0 && (
                  <div className="pt-4 border-t border-slate-800/40">
                    <p className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2">Sources Referenced</p>
                    <div className="flex flex-wrap gap-2">
                      {msg.sources.map((src: any, idx: number) => (
                        <div 
                          key={idx}
                          className="px-2.5 py-1 bg-slate-950/80 border border-slate-800 rounded-lg text-[9px] font-bold text-indigo-300 flex items-center gap-1.5"
                        >
                          <FileText size={10} />
                          <span>{src.doc_title || 'Document Link'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Confidence indicator badge & Feedback Loop */}
                {!isUser && !msg.isError && (
                  <div className="flex items-center justify-between mt-4">
                    {msg.confidence !== undefined ? (
                      <div className="flex items-center gap-1.5 text-[9px] font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-500/20 px-2 py-0.5 rounded-full w-max">
                        <ShieldCheck size={10} />
                        <span>{Math.round(msg.confidence)}% AI Confidence Score</span>
                      </div>
                    ) : <div />}
                    
                    <div className="flex items-center gap-2">
                      <button 
                        onClick={() => handleFeedback(i, true)}
                        className={`p-1.5 rounded-lg border transition-all ${msg.feedback === true ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'border-slate-800 text-slate-500 hover:text-emerald-400 hover:border-emerald-500/30 hover:bg-emerald-500/10'}`}
                      >
                        <ThumbsUp size={12} />
                      </button>
                      <button 
                        onClick={() => handleFeedback(i, false)}
                        className={`p-1.5 rounded-lg border transition-all ${msg.feedback === false ? 'bg-rose-500/20 border-rose-500/50 text-rose-400' : 'border-slate-800 text-slate-500 hover:text-rose-400 hover:border-rose-500/30 hover:bg-rose-500/10'}`}
                      >
                        <ThumbsDown size={12} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}

        {typing && (
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-slate-900 border border-slate-800 text-indigo-400 flex items-center justify-center shrink-0">
              <Bot size={14} className="animate-pulse" />
            </div>
            <div className="bg-slate-900 border border-slate-850 p-4 rounded-2xl flex gap-1 items-center">
              <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" />
              <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.2s]" />
              <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
        )}
      </div>

      {/* Input Form Box */}
      <div className="p-6 border-t border-slate-900 bg-slate-950/60 backdrop-blur-md">
        <form onSubmit={handleSend} className="relative max-w-4xl mx-auto w-full">
          <input
            type="text"
            placeholder="Ask anything about architecture specs or system design..."
            className="w-full bg-slate-950 border border-slate-800 rounded-[2rem] py-4 pl-8 pr-16 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all text-sm font-medium text-white"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="submit"
            disabled={!query.trim() || typing}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-900 disabled:text-slate-600 text-white flex items-center justify-center shadow-lg active:scale-95 transition-all"
          >
            {typing ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}
          </button>
        </form>
      </div>
    </div>
  );
}
