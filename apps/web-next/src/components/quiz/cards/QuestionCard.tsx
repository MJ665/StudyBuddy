'use client';

import RichText from './RichText';

export interface QCard {
  id: number;
  question: string;
  question_type: string; // mcq_single | mcq_multi | true_false | short_answer | essay
  options?: string[];
  content_format?: string; // text | latex | markdown
  media_urls?: string[] | null;
  points?: number;
}

interface Props {
  q: QCard;
  index: number;
  value: string | string[];
  onChange: (value: string | string[]) => void;
}

const TYPE_ACCENT: Record<string, string> = {
  mcq_single: 'border-l-sky-500',
  mcq_multi: 'border-l-indigo-500',
  true_false: 'border-l-teal-500',
  short_answer: 'border-l-amber-500',
  essay: 'border-l-purple-500',
};

const TYPE_LABEL: Record<string, string> = {
  mcq_single: 'Single choice',
  mcq_multi: 'Multiple choice',
  true_false: 'True / False',
  short_answer: 'Short answer',
  essay: 'Essay',
};

export default function QuestionCard({ q, index, value, onChange }: Props) {
  const fmt = q.content_format || 'text';
  const isMulti = q.question_type === 'mcq_multi';
  const selected: string[] = Array.isArray(value) ? value : value ? [value] : [];

  const toggleMulti = (opt: string) => {
    const set = new Set(selected);
    if (set.has(opt)) set.delete(opt);
    else set.add(opt);
    onChange(Array.from(set));
  };

  const optList = q.question_type === 'true_false' ? ['True', 'False'] : q.options || [];

  return (
    <div className={`rounded-xl bg-slate-900 border border-slate-800 border-l-4 ${TYPE_ACCENT[q.question_type] || 'border-l-slate-600'} p-5 mb-5`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-slate-500 text-xs font-bold">Q{index + 1}</span>
        <span className="text-[10px] uppercase tracking-widest text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
          {TYPE_LABEL[q.question_type] || q.question_type} · {q.points ?? 1} pt
        </span>
      </div>

      <div className="text-slate-100 mb-4 leading-relaxed">
        <RichText content={q.question} format={fmt} />
      </div>

      {q.media_urls?.map((u) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={u} src={u} alt="" className="max-w-full rounded-lg mb-4 border border-slate-800" />
      ))}

      {(q.question_type === 'short_answer') && (
        <input
          className="w-full rounded-lg bg-slate-800 border border-slate-700 px-4 py-2.5 text-sm focus:outline-none focus:border-amber-500"
          placeholder="Type your brief answer…"
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {(q.question_type === 'essay') && (
        <textarea
          className="w-full rounded-lg bg-slate-800 border border-slate-700 px-4 py-3 text-sm min-h-[140px] focus:outline-none focus:border-purple-500"
          placeholder="Write your answer…"
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {(q.question_type === 'mcq_single' || q.question_type === 'true_false' || isMulti) && (
        <div className="space-y-2">
          {optList.map((opt) => {
            const checked = isMulti ? selected.includes(opt) : value === opt;
            return (
              <label
                key={opt}
                className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 cursor-pointer transition ${
                  checked ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700 hover:border-slate-600'
                }`}
              >
                <input
                  type={isMulti ? 'checkbox' : 'radio'}
                  name={`q-${q.id}`}
                  checked={checked}
                  onChange={() => (isMulti ? toggleMulti(opt) : onChange(opt))}
                  className="accent-emerald-500"
                />
                <span className="text-sm text-slate-200">
                  <RichText content={opt} format={fmt} />
                </span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
