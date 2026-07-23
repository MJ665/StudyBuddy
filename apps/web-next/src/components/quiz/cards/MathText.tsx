'use client';

import katex from 'katex';

// Renders question/option content. For content_format="latex" it renders inline
// ($…$) and display ($$…$$) math with KaTeX and leaves the rest as text.
// The consuming page must import 'katex/dist/katex.min.css' once.

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderMixedLatex(content: string): string {
  // Split on $$…$$ (display) and $…$ (inline), rendering math segments.
  const parts = content.split(/(\$\$[^$]+\$\$|\$[^$]+\$)/g);
  return parts
    .map((part) => {
      if (part.startsWith('$$') && part.endsWith('$$')) {
        try {
          return katex.renderToString(part.slice(2, -2), { throwOnError: false, displayMode: true });
        } catch {
          return escapeHtml(part);
        }
      }
      if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        try {
          return katex.renderToString(part.slice(1, -1), { throwOnError: false });
        } catch {
          return escapeHtml(part);
        }
      }
      return escapeHtml(part);
    })
    .join('');
}

// Renamed from RichText → MathText: this is the KaTeX/math renderer for
// typed question cards; the code-block renderer lives in common/RichText.
export default function MathText({ content, format = 'text' }: { content: string; format?: string }) {
  if (!content) return null;
  if (format === 'latex') {
    return <span dangerouslySetInnerHTML={{ __html: renderMixedLatex(content) }} />;
  }
  return <span className="whitespace-pre-wrap">{content}</span>;
}
