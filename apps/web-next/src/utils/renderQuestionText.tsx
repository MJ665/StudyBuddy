import React from 'react';

/**
 * Markdown-lite renderer for question text.
 * Handles:
 *  1. Backtick-wrapped inline code → styled <code> chips
 *  2. Newlines → <br /> for multi-line questions
 *
 * This is a lightweight frontend-only parser — no dependency on
 * react-markdown or prism.js. For full code blocks, the existing
 * RichText component handles triple-backtick fenced blocks.
 */
export function renderQuestionText(text: string): React.ReactNode {
  if (!text) return null;

  // Split on backtick-wrapped segments (single backtick only)
  const parts = text.split(/(`[^`]+`)/g);

  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('`') && part.endsWith('`')) {
          const code = part.slice(1, -1);
          return (
            <code
              key={i}
              className="bg-slate-700/60 px-2 py-0.5 rounded-md text-indigo-300
                         font-mono text-[0.9em] border border-slate-600/40 inline-block"
            >
              {code}
            </code>
          );
        }
        // Preserve newlines as <br> for multi-line questions
        return part.split('\n').map((line, j, arr) => (
          <React.Fragment key={`${i}-${j}`}>
            {line}
            {j < arr.length - 1 && <br />}
          </React.Fragment>
        ));
      })}
    </>
  );
}
