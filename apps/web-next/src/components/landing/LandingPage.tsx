'use client';

/**
 * StudyBuddy marketing home (server-rendered content, client for animations).
 * Enterprise / contact-led: CTAs are "Sign in" (/login) and "Request a demo"
 * (/contact-me) — no self-serve signup. Dark premium theme matching the app;
 * responsive down to 390px (no horizontal overflow).
 */
import { motion } from 'motion/react';
import {
  ArrowRight, BrainCircuit, ClipboardCheck, Code2, ShieldCheck, Sparkles,
  Users, LineChart, MessageSquare, GraduationCap, UserCog, Building2,
  Trophy, FileText, Layers, Lock, Zap, CheckCircle2,
} from 'lucide-react';

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-80px' },
  transition: { duration: 0.5, ease: 'easeOut' as const },
};

function SignInButton({ className = '' }: { className?: string }) {
  return (
    <a
      href="/login"
      className={`inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-600/25 transition-all active:scale-95 ${className}`}
    >
      Sign in <ArrowRight size={16} />
    </a>
  );
}

function DemoButton({ className = '' }: { className?: string }) {
  return (
    <a
      href="/contact-me"
      className={`inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 px-5 py-3 text-sm font-bold text-slate-200 transition-all active:scale-95 ${className}`}
    >
      Request a demo
    </a>
  );
}

// ── Nav ──────────────────────────────────────────────────────────────────────
function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-[#0c1324]/80 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 md:px-8">
        <a href="/" className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/images/logo.png" alt="StudyBuddy" className="h-8 w-8 rounded-lg object-cover" />
          <span className="text-lg font-black tracking-tight text-white">StudyBuddy</span>
        </a>
        <div className="hidden items-center gap-7 text-sm font-semibold text-slate-400 md:flex">
          <a href="#products" className="hover:text-white transition-colors">Products</a>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#how" className="hover:text-white transition-colors">How it works</a>
          <a href="#who" className="hover:text-white transition-colors">Who it's for</a>
        </div>
        <div className="flex items-center gap-2">
          <a href="/contact-me" className="hidden px-3 py-2 text-sm font-semibold text-slate-300 hover:text-white transition-colors sm:block">Contact</a>
          <SignInButton />
        </div>
      </nav>
    </header>
  );
}

// ── Hero ─────────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* decorative glows — clipped so they never cause horizontal scroll */}
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[900px] max-w-[140vw] -translate-x-1/2 rounded-full bg-indigo-600/15 blur-[130px]" />
      <div className="pointer-events-none absolute top-40 right-[-10%] h-[380px] w-[380px] rounded-full bg-emerald-500/10 blur-[120px]" />

      <div className="relative mx-auto max-w-5xl px-5 pt-20 pb-16 text-center md:px-8 md:pt-28">
        <motion.div {...fadeUp} className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-[11px] font-bold uppercase tracking-widest text-indigo-300">
          <Sparkles size={13} /> Assess · Retain · Grow — one platform
        </motion.div>

        <motion.h1 {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.05 }}
          className="mx-auto max-w-3xl text-4xl font-black leading-[1.08] tracking-tight text-white sm:text-5xl md:text-6xl">
          Assess your people.
          <br />
          <span className="bg-gradient-to-r from-indigo-300 via-violet-300 to-emerald-300 bg-clip-text text-transparent">
            Keep the knowledge they carry.
          </span>
        </motion.h1>

        <motion.p {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.1 }}
          className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg">
          StudyBuddy is the enterprise platform to <strong className="text-slate-200">assess and grow every employee</strong> —
          quizzes, coding, proctored exams — and to <strong className="text-slate-200">retain the knowledge of the people who leave</strong>
          {' '}through AI-powered, cited knowledge transfer.
        </motion.p>

        <motion.div {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.15 }}
          className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <SignInButton className="w-full sm:w-auto" />
          <DemoButton className="w-full sm:w-auto" />
        </motion.div>

        <motion.div {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.2 }}
          className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs font-medium text-slate-500">
          <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={14} className="text-emerald-400" /> One unified assessment engine</span>
          <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={14} className="text-emerald-400" /> Cited RAG knowledge base</span>
          <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={14} className="text-emerald-400" /> Single-enterprise, RBAC-scoped</span>
        </motion.div>
      </div>
    </section>
  );
}

// ── Problem → Solution ───────────────────────────────────────────────────────
function Problem() {
  const points = [
    { icon: <BrainCircuit size={20} />, title: 'Knowledge walks out the door', body: 'When a senior engineer resigns, the “why” behind years of decisions leaves with them. Wikis go stale; nobody documents in time.' },
    { icon: <Layers size={20} />, title: 'Assessment is fragmented', body: 'Quizzes here, coding tests there, exams in a third tool — no single view of who is ready, at the learner, batch, or executive level.' },
    { icon: <LineChart size={20} />, title: 'No line of sight on readiness', body: 'Leaders can’t answer “is this cohort ready?” or “what did we lose when they left?” without stitching together spreadsheets.' },
  ];
  return (
    <section className="mx-auto max-w-6xl px-5 py-16 md:px-8 md:py-24">
      <motion.div {...fadeUp} className="mx-auto mb-12 max-w-2xl text-center">
        <p className="mb-3 text-xs font-black uppercase tracking-widest text-rose-400">The problem</p>
        <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">Two expensive gaps in every services company</h2>
      </motion.div>
      <div className="grid gap-5 md:grid-cols-3">
        {points.map((p, i) => (
          <motion.div key={p.title} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.06 }}
            className="rounded-3xl border border-white/5 bg-slate-900/50 p-7">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-400">{p.icon}</div>
            <h3 className="mb-2 text-lg font-bold text-white">{p.title}</h3>
            <p className="text-sm leading-relaxed text-slate-400">{p.body}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

// ── Two products ─────────────────────────────────────────────────────────────
function Products() {
  return (
    <section id="products" className="mx-auto max-w-6xl px-5 py-16 md:px-8 md:py-24">
      <motion.div {...fadeUp} className="mx-auto mb-12 max-w-2xl text-center">
        <p className="mb-3 text-xs font-black uppercase tracking-widest text-indigo-400">One platform, two products</p>
        <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">Everything shares the same org, people, auth & AI core</h2>
      </motion.div>
      <div className="grid gap-6 lg:grid-cols-2">
        <motion.div {...fadeUp} className="relative overflow-hidden rounded-[2rem] border border-indigo-500/20 bg-gradient-to-b from-indigo-500/[0.08] to-transparent p-8">
          <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/15 text-indigo-300"><ClipboardCheck size={24} /></div>
          <h3 className="text-2xl font-black text-white">Assess</h3>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">One engine for every kind of evaluation — behavior is configuration, not separate tools.</p>
          <ul className="mt-6 space-y-3 text-sm text-slate-300">
            {['MCQ, descriptive, coding (AI-evaluated) & config questions', 'Practice quizzes, proctored exams & daily challenges — one engine', 'Assignments down the org tree; auto + AI grading via a durable queue', 'Analytics from learner → batch → executive, with exports'].map((t) => (
              <li key={t} className="flex gap-2.5"><CheckCircle2 size={17} className="mt-0.5 shrink-0 text-indigo-400" />{t}</li>
            ))}
          </ul>
        </motion.div>

        <motion.div {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.08 }}
          className="relative overflow-hidden rounded-[2rem] border border-emerald-500/20 bg-gradient-to-b from-emerald-500/[0.08] to-transparent p-8">
          <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-300"><BrainCircuit size={24} /></div>
          <h3 className="text-2xl font-black text-white">Knowledge Transfer</h3>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">Capture what people know before they leave — and make it answerable.</p>
          <ul className="mt-6 space-y-3 text-sm text-slate-300">
            {['Experts document the what/how/why/when of their work', 'Mentors review & approve — approval auto-indexes to pgvector', 'Cited RAG chatbot answers, grounded in approved knowledge only', 'Structured exit-handoff workflow with coverage reporting'].map((t) => (
              <li key={t} className="flex gap-2.5"><CheckCircle2 size={17} className="mt-0.5 shrink-0 text-emerald-400" />{t}</li>
            ))}
          </ul>
        </motion.div>
      </div>
    </section>
  );
}

// ── Feature grid ─────────────────────────────────────────────────────────────
function Features() {
  const features = [
    { icon: <Zap size={20} />, title: 'Unified assessment engine', body: 'Practice, timed, proctored, daily — all one engine driven by settings, not forked code paths.' },
    { icon: <Code2 size={20} />, title: 'AI-evaluated coding', body: 'Assess real code (and descriptive answers) with LLM grading — no execution infra to run.' },
    { icon: <ShieldCheck size={20} />, title: 'Proctored exams', body: 'Server-side timing, deterministic shuffling, tab/copy/focus flags, optional webcam.' },
    { icon: <MessageSquare size={20} />, title: 'Cited RAG chatbot', body: 'ChatGPT-style, streamed, markdown-rich answers grounded in your approved knowledge, with sources + confidence.' },
    { icon: <FileText size={20} />, title: 'Exit handoff', body: 'Auto-built checklists capture a departing employee’s knowledge before their last day.' },
    { icon: <Lock size={20} />, title: 'Enterprise RBAC', body: 'A flexible OrgUnit tree (org → dept → vertical → batch → group) scopes every action; 404-not-403.' },
    { icon: <LineChart size={20} />, title: 'Analytics & reports', body: 'Readiness, distributions and AI executive summaries — learner to boardroom, exportable.' },
    { icon: <Trophy size={20} />, title: 'Engagement built-in', body: 'Leaderboards, streaks, daily challenges and discussions keep people coming back.' },
  ];
  return (
    <section id="features" className="mx-auto max-w-6xl px-5 py-16 md:px-8 md:py-24">
      <motion.div {...fadeUp} className="mx-auto mb-12 max-w-2xl text-center">
        <p className="mb-3 text-xs font-black uppercase tracking-widest text-indigo-400">Features</p>
        <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">Enterprise-grade, out of the box</h2>
      </motion.div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {features.map((f, i) => (
          <motion.div key={f.title} {...fadeUp} transition={{ ...fadeUp.transition, delay: (i % 4) * 0.05 }}
            className="rounded-3xl border border-white/5 bg-slate-900/50 p-6 transition-colors hover:border-indigo-500/25">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-300">{f.icon}</div>
            <h3 className="mb-1.5 text-base font-bold text-white">{f.title}</h3>
            <p className="text-[13px] leading-relaxed text-slate-400">{f.body}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

// ── How it works ─────────────────────────────────────────────────────────────
function HowItWorks() {
  const assess = ['Author or AI-generate banks', 'Publish & assign down the org tree', 'Learners take (any question type)', 'Grade + analyze → reports'];
  const kt = ['Experts document their work', 'Mentors review & approve', 'Approved knowledge auto-indexed', 'Anyone asks → cited answers'];
  return (
    <section id="how" className="mx-auto max-w-6xl px-5 py-16 md:px-8 md:py-24">
      <motion.div {...fadeUp} className="mx-auto mb-12 max-w-2xl text-center">
        <p className="mb-3 text-xs font-black uppercase tracking-widest text-indigo-400">How it works</p>
        <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">Two simple loops</h2>
      </motion.div>
      <div className="grid gap-6 lg:grid-cols-2">
        {[{ label: 'Assess', color: 'indigo', steps: assess }, { label: 'Knowledge Transfer', color: 'emerald', steps: kt }].map((flow) => (
          <motion.div key={flow.label} {...fadeUp} className="rounded-[2rem] border border-white/5 bg-slate-900/40 p-8">
            <h3 className={`mb-6 text-sm font-black uppercase tracking-widest ${flow.color === 'indigo' ? 'text-indigo-400' : 'text-emerald-400'}`}>{flow.label}</h3>
            <ol className="space-y-4">
              {flow.steps.map((s, i) => (
                <li key={s} className="flex items-center gap-4">
                  <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-black ${flow.color === 'indigo' ? 'bg-indigo-500/15 text-indigo-300' : 'bg-emerald-500/15 text-emerald-300'}`}>{i + 1}</span>
                  <span className="text-sm font-medium text-slate-200">{s}</span>
                </li>
              ))}
            </ol>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

// ── Personas ─────────────────────────────────────────────────────────────────
function Personas() {
  const roles = [
    { icon: <GraduationCap size={20} />, title: 'Learners', body: 'Take assigned assessments, see progress & streaks, climb the leaderboard, ask the KT bot.' },
    { icon: <Users size={20} />, title: 'Mentors', body: 'One inbox: review learner performance and approve knowledge docs — no split-brain.' },
    { icon: <UserCog size={20} />, title: 'L&D Admins', body: 'Build the org tree, bulk-import users, assign curriculum, read org-wide analytics.' },
    { icon: <Building2 size={20} />, title: 'Executives', body: 'Readiness reports, AI executive summaries, and KT coverage per project — exportable.' },
  ];
  return (
    <section id="who" className="mx-auto max-w-6xl px-5 py-16 md:px-8 md:py-24">
      <motion.div {...fadeUp} className="mx-auto mb-12 max-w-2xl text-center">
        <p className="mb-3 text-xs font-black uppercase tracking-widest text-indigo-400">Who it's for</p>
        <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">Built for the whole org</h2>
      </motion.div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {roles.map((r, i) => (
          <motion.div key={r.title} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.05 }}
            className="rounded-3xl border border-white/5 bg-slate-900/50 p-6 text-center">
            <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-white/5 text-indigo-300">{r.icon}</div>
            <h3 className="mb-1.5 text-base font-bold text-white">{r.title}</h3>
            <p className="text-[13px] leading-relaxed text-slate-400">{r.body}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

// ── CTA band ─────────────────────────────────────────────────────────────────
function CTA() {
  return (
    <section className="mx-auto max-w-6xl px-5 py-16 md:px-8 md:py-24">
      <motion.div {...fadeUp} className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-gradient-to-br from-indigo-600/20 via-slate-900 to-emerald-600/10 px-6 py-14 text-center md:px-16">
        <div className="pointer-events-none absolute -top-24 left-1/2 h-64 w-[600px] max-w-[120vw] -translate-x-1/2 rounded-full bg-indigo-500/20 blur-[100px]" />
        <h2 className="relative text-3xl font-black tracking-tight text-white sm:text-4xl">Ready to assess your teams and keep their knowledge?</h2>
        <p className="relative mx-auto mt-4 max-w-xl text-slate-300">Accounts are provisioned by your L&D admins. Sign in if you already have one, or request a walkthrough.</p>
        <div className="relative mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <SignInButton className="w-full sm:w-auto" />
          <DemoButton className="w-full sm:w-auto" />
        </div>
      </motion.div>
    </section>
  );
}

// ── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="border-t border-white/5">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-10 md:flex-row md:px-8">
        <div className="flex items-center gap-2.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/images/logo.png" alt="StudyBuddy" className="h-7 w-7 rounded-lg object-cover" />
          <span className="text-sm font-black text-white">StudyBuddy</span>
          <span className="text-xs text-slate-600">· Assess. Retain. Grow.</span>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm font-medium text-slate-400">
          <a href="/login" className="hover:text-white transition-colors">Sign in</a>
          <a href="/contact-me" className="hover:text-white transition-colors">Contact</a>
          <a href="/privacy" className="hover:text-white transition-colors">Privacy</a>
          <a href="/terms" className="hover:text-white transition-colors">Terms</a>
        </div>
      </div>
      <p className="pb-8 text-center text-xs text-slate-600">© {new Date().getFullYear()} StudyBuddy. Enterprise assessment & knowledge transfer.</p>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-[#0c1324] text-white antialiased">
      <Nav />
      <main>
        <Hero />
        <Problem />
        <Products />
        <Features />
        <HowItWorks />
        <Personas />
        <CTA />
      </main>
      <Footer />
    </div>
  );
}
