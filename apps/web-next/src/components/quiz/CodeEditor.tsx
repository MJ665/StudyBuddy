import React, { useState, useEffect } from 'react';
import Editor, { loader } from '@monaco-editor/react';
import { 
  CheckCircle2, 
  Lightbulb, 
  Sparkles, 
  ChevronRight, 
  RotateCcw, 
  ChevronDown,
  Info,
  Terminal,
  Copy,
  Settings,
  Type,
  Palette,
  X
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ApiService, { AIResponseEnvelope } from '../../services/ApiService';
import { useToast } from '../ui/Toast';

// Configure Monaco to load extra languages from CDN
loader.config({
  paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.43.0/min/vs' }
});

const THEMES = [
  { id: 'vs-dark', name: 'Standard Dark' },
  { id: 'hc-black', name: 'High Contrast' },
  { id: 'light', name: 'Standard Light' }
];

const FONT_SIZES = [12, 13, 14, 15, 16, 18, 20];

export default function CodeEditor({ question, onFinish }: any) {
  const { toast } = useToast();
  const [supportedLanguages, setSupportedLanguages] = useState<any[]>([]);
  const [code, setCode] = useState(question.initial_code || "");
  const [evalResult, setEvalResult] = useState<any>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [hints, setHints] = useState<string[]>([]);
  const [loadingHint, setLoadingHint] = useState(false);
  const [showCriteria, setShowCriteria] = useState(false);
  
  // Custom Settings
  const [language, setLanguage] = useState(question.language?.toLowerCase() || 'python');
  const [theme, setTheme] = useState('vs-dark');
  const [fontSize, setFontSize] = useState(14);
  const [showSettings, setShowSettings] = useState(false);

  const [languagesByCategory, setLanguagesByCategory] = useState<Record<string, any[]>>({});

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const configReq = ApiService.getSystemConfig();
        const langReq = ApiService.getProgrammingLanguages();
        
        const [config, langRes] = await Promise.all([configReq, langReq]);
        
        // Config processing
        if ((config as any).languages_by_category) {
            // Still parse config just in case
        }
        
        // Safely extract from AIResponseEnvelope
        const langData = langRes?.data || langRes;
        
        setSupportedLanguages(langData.languages || config.supported_languages || []);
        if (langData.categories) {
          setLanguagesByCategory(langData.categories);
        }
      } catch (err) {
        console.error("Failed to load system config or languages", err);
      }
    };
    fetchConfig();
  }, []);

  // Auto-set initial code based on language if empty
  useEffect(() => {
    if (!code) {
      resetCode();
    }
  }, [language]);

  const resetCode = () => {
    let initial = question.initial_code || "";
    if (!initial) {
      setCode("");
      toast('info', 'No starter code provided. Write your solution from scratch.');
      return;
    }
    setCode(initial);
    toast('info', 'Code reset to initial state');
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    toast('success', 'Code copied to clipboard');
  };

  const handleEvaluate = async () => {
    setIsEvaluating(true);
    setEvalResult(null);
    setOutput("Initializing Enterprise AI evaluation engine...\nContextualizing for " + language + "...\nAnalyzing code structure and best practices...\nRunning validation rubrics...");
    try {
      // Send code, language, and question ID
      const res = await ApiService.evaluateCode(question.id, code, language, 0) as AIResponseEnvelope;
      const data = res.data?.evaluation || (res as any).evaluation || res; 
      setEvalResult(data);
      
      const verdict = data.passed ? 'Likely correct' : 'Needs work';
      setOutput(`AI Assessment Complete (code was reviewed by AI, not executed against test cases).\nScore: ${data.score}%\nAI Verdict: ${verdict}\nGrade: ${data.grade}\n\nFeedback:\n${data.feedback}`);

      if (data.passed) toast('success', `AI score: ${data.score}% — criteria look met.`);
      else toast('warning', `AI score: ${data.score}% — review the suggestions.`);
    } catch (err: any) {
      setOutput(`Error: ${err.message}`);
      toast('error', `Evaluation failed: ${err.message}`);
    } finally {
      setIsEvaluating(false);
    }
  };

  const fetchHint = async () => {
    if (hintLevel >= (question.max_hints_allowed || 3)) {
      toast('warning', 'Max hints exhausted for this sector.');
      return;
    }
    setLoadingHint(true);
    try {
      // Pass current code and language for context-aware hints
      const res = await ApiService.getHint(question.id, hintLevel + 1, code, language) as AIResponseEnvelope;
      const hintData = res.data || (res as any).hint || res;
      const hintText = hintData.hint_text || "No hint available";
      setHints([...hints, hintText]);
      setHintLevel(hintLevel + 1);
      toast('info', `Hint level ${hintLevel + 1} received.`);
    } catch (err: any) {
      toast('error', `Hint failed: ${err.message}`);
    } finally {
      setLoadingHint(false);
    }
  };

  const handleLanguageChange = (langId: string) => {
    const lang = supportedLanguages.find((l: any) => l.id === langId);
    if (lang) {
      setLanguage(lang.id);
      localStorage.setItem('studyhub_preferred_lang', lang.id);
    }
  };

  const getMonacoLang = (lang: string) => {
    const found = supportedLanguages.find(l => l.id === lang.toLowerCase());
    return found ? found.monaco_language : lang.toLowerCase();
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl">
      {/* HEADER */}
      <div className="flex items-center justify-between px-8 py-5 bg-slate-900 border-b border-white/5 z-30">
        <div className="flex items-center gap-4">
           <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center text-brand-primary border border-brand-primary/20">
              <Sparkles size={20} />
           </div>
           <div>
              <h2 className="text-lg font-black text-white">{question.title}</h2>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                    AI Intellisense: {supportedLanguages.find(l => l.id === language)?.name || language}
                  </p>
                </div>
                {/* Language Selector Inline */}
                <div className="relative group/lang">
                  <button className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-brand-primary hover:text-white transition-colors">
                    Switch Engine <ChevronDown size={10} />
                  </button>
                  <div className="absolute top-full left-0 mt-2 w-64 bg-slate-900 border border-white/10 rounded-2xl shadow-2xl opacity-0 invisible group-hover/lang:opacity-100 group-hover/lang:visible transition-all z-50 overflow-y-auto max-h-[70vh] p-2 custom-scrollbar">
                    {Object.keys(languagesByCategory).length > 0 ? (
                      Object.entries(languagesByCategory).map(([category, langs]) => (
                        <div key={category} className="mb-2 last:mb-0">
                          <div className="px-3 py-1 text-[8px] font-black uppercase tracking-[0.2em] text-slate-500 bg-white/5 rounded-lg mb-1">
                            {category}
                          </div>
                          {langs.map((l: any) => (
                            <button 
                              key={l.id} 
                              onClick={() => handleLanguageChange(l.id)}
                              className={`w-full text-left px-3 py-2 rounded-lg text-[10px] font-bold uppercase tracking-widest hover:bg-white/5 transition-colors ${language === l.id ? 'text-brand-primary bg-brand-primary/5' : 'text-slate-400'}`}
                            >
                              {l.name}
                            </button>
                          ))}
                        </div>
                      ))
                    ) : (
                      supportedLanguages.map(l => (
                        <button 
                          key={l.id} 
                          onClick={() => handleLanguageChange(l.id)}
                          className={`w-full text-left px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest hover:bg-white/5 transition-colors ${language === l.id ? 'text-brand-primary bg-brand-primary/5' : 'text-slate-400'}`}
                        >
                          {l.name}
                        </button>
                      ))
                    )}
                  </div>
                </div>
              </div>
           </div>
        </div>
        
        <div className="flex items-center gap-3">
           <button 
             onClick={copyToClipboard}
             className="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-xl transition-all border border-white/5 group"
             title="Copy Source Code"
           >
             <Copy size={18} />
           </button>
           <button 
             onClick={resetCode}
             className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-all border border-white/5 group"
           >
             <RotateCcw size={14} className="group-hover:rotate-[-45deg] transition-all" />
             <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Reset</span>
           </button>
           <button 
             onClick={() => setShowSettings(!showSettings)}
             className={`p-2.5 rounded-xl border transition-all ${showSettings ? 'bg-brand-primary border-brand-primary text-slate-950' : 'bg-slate-800 border-slate-700 text-slate-400'}`}
             title="Editor Configurations"
           >
             <Settings size={18} />
           </button>
           <button 
             onClick={() => setShowCriteria(!showCriteria)}
             className={`p-2.5 rounded-xl border transition-all ${showCriteria ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-800 border-slate-700 text-slate-400'}`}
             title="Mission Requirements"
           >
             <Info size={18} />
           </button>
           <button 
             onClick={handleEvaluate}
             disabled={isEvaluating}
             className="bg-brand-primary text-slate-950 px-6 py-2.5 rounded-xl font-black flex items-center gap-2 shadow-lg hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-50"
           >
             {isEvaluating ? (
               <div className="animate-spin h-4 w-4 border-2 border-slate-950 border-t-transparent rounded-full" />
             ) : (
               <>Run Test <Terminal size={18} /></>
             )}
           </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
        {/* Settings Modal Overlay */}
        <AnimatePresence>
          {showSettings && (
            <motion.div 
              initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
              className="absolute right-6 top-6 z-[60] bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl w-64"
            >
              <div className="flex items-center justify-between mb-6">
                <h4 className="text-[10px] font-black uppercase tracking-widest text-brand-primary">Configurations</h4>
                <button onClick={() => setShowSettings(false)} className="text-slate-500 hover:text-white"><X size={14} /></button>
              </div>
              
              <div className="space-y-6">
                <div>
                  <div className="flex items-center gap-2 mb-3 text-slate-400">
                    <Palette size={12} />
                    <span className="text-[10px] font-black uppercase tracking-widest">Environment Theme</span>
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    {THEMES.map(t => (
                      <button 
                        key={t.id} 
                        onClick={() => setTheme(t.id)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${theme === t.id ? 'bg-brand-primary text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-2 mb-3 text-slate-400">
                    <Type size={12} />
                    <span className="text-[10px] font-black uppercase tracking-widest">Terminal Font Size</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {FONT_SIZES.map(s => (
                      <button 
                        key={s} 
                        onClick={() => setFontSize(s)}
                        className={`w-8 h-8 rounded-lg text-[10px] font-black transition-all ${fontSize === s ? 'bg-brand-primary text-slate-950' : 'bg-slate-800 text-slate-400'}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* EDITOR */}
        <div className="flex-1 flex flex-col relative overflow-hidden bg-[#1e1e1e]">
           <AnimatePresence>
             {showCriteria && (
               <motion.div 
                 initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
                 className="absolute top-4 left-4 right-4 z-50 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-3xl p-6 shadow-2xl"
               >
                 <h4 className="text-[10px] font-black uppercase tracking-widest text-brand-primary mb-4 flex items-center justify-between">
                   Mission Directives
                   <button onClick={() => setShowCriteria(false)} className="text-slate-500 hover:text-white"><X size={14} /></button>
                 </h4>
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                   {question.evaluation_criteria?.map((c: string, i: number) => (
                     <div key={i} className="flex gap-2 text-xs text-slate-400 bg-white/5 p-3 rounded-xl border border-white/5">
                       <CheckCircle2 size={14} className="text-brand-primary shrink-0" />
                       {c}
                     </div>
                   ))}
                   {(!question.evaluation_criteria || question.evaluation_criteria.length === 0) && (
                     <p className="text-xs text-slate-500 italic">No specific criteria defined for this assessment.</p>
                   )}
                 </div>
               </motion.div>
             )}
           </AnimatePresence>

           <Editor
             height="100%"
             language={getMonacoLang(language)}
             theme={theme}
             value={code}
             onChange={(val) => setCode(val || '')}
             options={{
               fontSize: fontSize,
               minimap: { enabled: true },
               scrollBeyondLastLine: false,
               automaticLayout: true,
               tabSize: 2,
               wordWrap: 'on',
               lineNumbers: 'on',
               glyphMargin: true,
               folding: true,
               bracketPairColorization: { enabled: true },
               suggestOnTriggerCharacters: true,
               parameterHints: { enabled: true },
               quickSuggestions: { other: true, comments: true, strings: true },
               formatOnPaste: true,
               formatOnType: true,
               fixedOverflowWidgets: true,
               fontFamily: "'Fira Code', 'JetBrains Mono', monospace",
               fontLigatures: true,
               cursorSmoothCaretAnimation: "on",
               smoothScrolling: true,
               scrollbar: {
                 verticalScrollbarSize: 10,
                 horizontalScrollbarSize: 10
               }
             }}
           />

            {/* OUTPUT CONSOLE */}
            <AnimatePresence>
               {output && (
                 <motion.div 
                   initial={{ y: 100 }}
                   animate={{ y: 0 }}
                   exit={{ y: 100 }}
                   className="absolute bottom-0 left-0 right-0 h-48 bg-slate-900/95 backdrop-blur-md border-t border-white/10 z-20 flex flex-col"
                 >
                    <div className="flex items-center justify-between px-6 py-2 border-b border-white/5 bg-slate-950/50">
                       <div className="flex items-center gap-2">
                          <Terminal size={12} className="text-brand-primary" />
                          <span className="text-[9px] font-black uppercase tracking-[0.2em] text-slate-400">Terminal Intelligence Output</span>
                       </div>
                       <button onClick={() => setOutput(null)} className="text-slate-600 hover:text-white transition-colors">
                          <X size={14} />
                       </button>
                    </div>
                    <div className="p-4 font-mono text-xs text-slate-300 overflow-y-auto whitespace-pre-wrap selection:bg-brand-primary/30">
                       {output}
                    </div>
                 </motion.div>
               )}
            </AnimatePresence>

           {/* HINTS */}
           <div className="absolute bottom-6 left-6 right-6 pointer-events-none flex justify-center gap-3">
              {hints.map((h, i) => (
                <div key={i} className="group relative pointer-events-auto">
                   <div className="bg-indigo-600 text-white p-3 rounded-2xl shadow-lg cursor-help border border-white/10">
                      <Lightbulb size={18} />
                   </div>
                   <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-4 w-72 bg-slate-900 border border-indigo-500/30 p-4 rounded-2xl shadow-2xl opacity-0 group-hover:opacity-100 transition-all text-sm text-slate-300">
                      <p className="font-black text-brand-primary text-[10px] mb-2 uppercase tracking-widest">Protocol Hint L-{i + 1}</p>
                      {h}
                   </div>
                </div>
              ))}
              {hintLevel < (question.max_hints_allowed || 3) && (
                <button 
                  onClick={fetchHint} 
                  disabled={loadingHint} 
                  className="bg-slate-900/90 hover:bg-slate-800 border border-white/10 text-white px-5 py-3 rounded-2xl pointer-events-auto flex items-center gap-3 backdrop-blur-md transition-all shadow-xl"
                >
                   {loadingHint ? (
                     <div className="animate-spin h-4 w-4 border-2 border-white/30 border-t-white rounded-full" />
                   ) : (
                     <>
                        <div className="relative">
                          <Lightbulb size={16} className="text-amber-400" />
                          <span className="absolute -top-2 -right-2 w-4 h-4 bg-rose-500 text-[8px] font-black rounded-full flex items-center justify-center border-2 border-slate-900">
                            {(question.max_hints_allowed || 3) - hintLevel}
                          </span>
                        </div> 
                        <span className="text-[10px] font-black uppercase tracking-widest">Request Intel</span>
                     </>
                   )}
                </button>
              )}
           </div>
        </div>

        {/* SIDEBAR */}
        <div className="w-full lg:w-96 bg-slate-900 border-l border-white/5 flex flex-col">
           {evalResult ? (
             <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-8 space-y-6 overflow-y-auto w-full">
                <div className="text-center p-8 rounded-[2.5rem] bg-white/5 border border-white/5 relative overflow-hidden">
                   <div className={`absolute inset-0 opacity-5 pointer-events-none ${evalResult.passed ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                   <div className={`w-24 h-24 rounded-full mx-auto mb-6 flex items-center justify-center border-4 relative ${evalResult.passed ? 'border-emerald-500/50 bg-emerald-500/10 shadow-lg shadow-emerald-500/10' : 'border-rose-500/50 bg-rose-500/10 shadow-lg shadow-rose-500/10'}`}>
                      <span className={`text-3xl font-black ${evalResult.passed ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {evalResult.score}%
                      </span>
                   </div>
                   <h3 className="text-lg font-black text-white uppercase tracking-tight mb-1">{evalResult.passed ? 'Mission Success' : 'Directives Failed'}</h3>
                   <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">{evalResult.passed ? 'Logic Protocol Verified' : 'Refinement Mandatory'}</p>
                </div>

                <div className="space-y-2">
                  <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Judicial Verdict</span>
                  <div className="text-sm text-slate-300 leading-relaxed bg-slate-950 p-6 rounded-[1.5rem] border border-white/5 font-medium italic relative">
                    <span className="absolute top-4 left-4 text-indigo-500/20 text-4xl font-serif">"</span>
                    <p className="relative z-10">{evalResult.feedback}</p>
                    <span className="absolute bottom-2 right-4 text-indigo-500/20 text-4xl font-serif">"</span>
                  </div>
                </div>

                {evalResult.suggestions?.length > 0 && (
                  <div className="space-y-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Optimization Log</span>
                    <div className="space-y-2">
                      {evalResult.suggestions.map((s: string, i: number) => (
                        <div key={i} className="flex gap-3 p-3 bg-indigo-500/5 rounded-xl border border-indigo-500/10 text-xs text-indigo-300 group hover:bg-indigo-500/10 transition-colors">
                          <Sparkles size={14} className="shrink-0 group-hover:scale-110 transition-transform" /> 
                          <span className="font-medium">{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="pt-4 space-y-3">
                   {evalResult.passed ? (
                     <button onClick={() => onFinish(evalResult)} className="w-full py-5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-2xl font-black transition-all shadow-xl shadow-emerald-600/20 uppercase tracking-[0.2em] text-[10px]">
                       Proceed to Next Sector
                     </button>
                   ) : (
                     <button onClick={() => setEvalResult(null)} className="w-full py-5 bg-slate-800 hover:bg-slate-700 text-white rounded-2xl font-black transition-all border border-white/5 uppercase tracking-[0.2em] text-[10px]">
                       Reformulate Logic
                     </button>
                   )}
                </div>
             </motion.div>
           ) : (
             <div className="flex-1 flex flex-col items-center justify-center p-12 text-center opacity-30">
                <div className="w-20 h-20 bg-slate-950 border border-white/5 rounded-3xl flex items-center justify-center mb-8">
                  <Terminal size={40} className="text-slate-600" />
                </div>
                <h3 className="text-[10px] font-black text-white uppercase tracking-[0.3em]">Evaluation Idle</h3>
                <p className="text-[10px] text-slate-500 mt-4 leading-relaxed max-w-[200px] font-bold uppercase tracking-widest">Submit your code for high-fidelity multi-model rubric validation.</p>
             </div>
           )}
        </div>
      </div>
    </div>
  );
}
