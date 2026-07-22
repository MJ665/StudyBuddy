'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkToc from 'remark-toc';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check, Link, ExternalLink } from 'lucide-react';
import 'highlight.js/styles/github-dark.css';

interface EnterpriseMarkdownPreviewProps {
  content: string;
  showToc?: boolean;
  className?: string;
}

function CodeBlock({ children, className, ...props }: any) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : 'text';
  const codeString = String(children).replace(/\n$/, '');

  const handleCopy = () => {
    navigator.clipboard.writeText(codeString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!match) {
    return (
      <code className="px-1.5 py-0.5 bg-slate-800/80 text-indigo-300 rounded-md font-mono text-[0.875em] border border-slate-700/50">
        {children}
      </code>
    );
  }

  return (
    <div className="relative group my-6 rounded-2xl overflow-hidden border border-slate-800 shadow-xl shadow-black/20">
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-rose-500/70" />
          <div className="w-3 h-3 rounded-full bg-amber-500/70" />
          <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
          <span className="ml-3 text-[11px] font-mono font-bold text-slate-500 uppercase tracking-widest">
            {language}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-slate-500 hover:text-white transition-colors text-[11px] font-bold uppercase tracking-wider"
        >
          {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: 0,
          background: '#0d1117',
          padding: '1.5rem',
          fontSize: '0.875rem',
          lineHeight: '1.7',
        }}
        showLineNumbers={codeString.split('\n').length > 5}
      >
        {codeString}
      </SyntaxHighlighter>
    </div>
  );
}

export default function EnterpriseMarkdownPreview({ content, showToc = true, className = '' }: EnterpriseMarkdownPreviewProps) {
  return (
    <div className={`text-slate-300 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[
          rehypeSlug,
          [rehypeAutolinkHeadings, { behavior: 'wrap' }],
        ]}
        components={{
          code: CodeBlock,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
