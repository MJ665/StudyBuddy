'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';

/**
 * Rich markdown renderer for KT assistant responses — code blocks (highlighted),
 * tables, lists, blockquotes, links. Styled for the dark KT surface. Used for
 * both streamed and persisted messages so the output always "looks good".
 */
export function ChatMarkdown({ content }: { content: string }) {
  return (
    <div className="chat-md text-sm leading-relaxed break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc ml-5 mb-3 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal ml-5 mb-3 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          h1: ({ children }) => <h1 className="text-lg font-black text-white mt-4 mb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-bold text-white mt-4 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-bold text-slate-100 mt-3 mb-1.5">{children}</h3>,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-400 underline hover:text-indigo-300">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-indigo-500/40 pl-3 my-3 text-slate-400 italic">{children}</blockquote>
          ),
          code: ({ inline, className, children }: any) =>
            inline ? (
              <code className="px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300 text-[0.85em] font-mono">{children}</code>
            ) : (
              <code className={`${className || ''} block`}>{children}</code>
            ),
          pre: ({ children }) => (
            <pre className="my-3 p-3 rounded-xl bg-slate-950 border border-slate-800 overflow-x-auto text-[0.82em] leading-relaxed">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full text-xs border border-slate-800 rounded-lg overflow-hidden">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="px-3 py-2 bg-slate-900 text-left font-bold border-b border-slate-800">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-b border-slate-850">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
