import React from 'react';

/**
 * RichText — handles BOTH triple-backtick code blocks AND single-backtick inline code.
 *
 * Triple backticks (```...```) → <pre><code> blocks with syntax header
 * Single backticks (`...`)     → inline <code> chips with indigo styling
 * Newlines in regular text     → preserved via whitespace-pre-wrap
 */
export const RichText: React.FC<{ text: string; className?: string }> = ({ text, className = '' }) => {
  if (!text) return null;

  // Split the text by triple backticks first: ```[lang]\n<code>```
  const parts = text.split(/(```[\s\S]*?```)/g);

  return (
    <div className={`space-y-3 ${className}`}>
      {parts.map((part, idx) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          // It's a code block: strip the triple backticks
          const content = part.slice(3, -3);
          const lines = content.split('\n');
          
          // First line might be the language
          let lang = lines[0].trim();
          let codeLines = lines.slice(1);
          
          // If the first line has spaces, it's not a language tag
          if (lang.includes(' ') || !lang) {
            lang = '';
            codeLines = lines;
          }
          
          const codeContent = codeLines.join('\n').trim();
          
          return (
            <div key={idx} className="my-4 rounded-2xl overflow-hidden border border-white/10 bg-slate-900/80 shadow-2xl" onClick={e => e.stopPropagation()}>
              {lang && (
                <div className="bg-slate-800/50 px-4 py-2 border-b border-white/5 flex items-center justify-between">
                  <span className="text-[10px] font-black font-mono text-slate-500 uppercase tracking-widest">{lang}</span>
                  <div className="flex gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-slate-700" />
                    <div className="w-2 h-2 rounded-full bg-slate-700" />
                    <div className="w-2 h-2 rounded-full bg-slate-700" />
                  </div>
                </div>
              )}
              <div className="p-5 overflow-x-auto custom-scrollbar">
                <pre className="font-mono text-sm leading-relaxed text-indigo-300 selection:bg-indigo-500/30">
                  <code>{codeContent}</code>
                </pre>
              </div>
            </div>
          );
        } else {
          // It's regular text, handle inline code blocks and images
          return <span key={idx} className="whitespace-pre-wrap leading-relaxed">{renderMarkdownElements(part)}</span>;
        }
      })}
    </div>
  );
};

/**
 * Renders inline markdown elements:
 * 1. Single-backtick code: `code`
 * 2. Markdown images: ![alt](url)
 */
function renderMarkdownElements(text: string): React.ReactNode {
  // Split on single backticks OR markdown image syntax
  const parts = text.split(/(`[^`]+`|!\[.*?\]\(.*?\))/g);
  
  if (parts.length === 1) return text;

  return (
    <>
      {parts.map((part, i) => {
        // Handle Inline Code
        if (part.startsWith('`') && part.endsWith('`')) {
          const code = part.slice(1, -1);
          return (
            <code
              key={i}
              className="bg-indigo-500/10 px-2 py-0.5 rounded-md text-indigo-400
                         font-mono text-[0.95em] border border-indigo-500/20 mx-1"
            >
              {code}
            </code>
          );
        }
        
        // Handle Images
        if (part.startsWith('![') && part.includes('](') && part.endsWith(')')) {
          const altMatch = part.match(/!\[(.*?)\]/);
          const urlMatch = part.match(/\((.*?)\)/);
          const alt = altMatch ? altMatch[1] : 'image';
          const url = urlMatch ? urlMatch[1] : '';
          
          return (
            <span key={i} className="block my-4">
              <img 
                src={url} 
                alt={alt} 
                className="max-w-full rounded-2xl border border-white/10 shadow-xl 
                           hover:border-indigo-500/30 transition-colors" 
              />
              {alt && alt !== 'image' && (
                <span className="block text-center text-[10px] text-slate-500 mt-2 italic">
                  {alt}
                </span>
              )}
            </span>
          );
        }
        
        return <React.Fragment key={i}>{part}</React.Fragment>;
      })}
    </>
  );
}
