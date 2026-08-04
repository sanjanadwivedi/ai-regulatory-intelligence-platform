import React from 'react';
import {
  ShieldCheck,
  GitFork,
  ArrowRight,
  Sparkles,
  Bot,
  Activity,
  Lock,
  Globe
} from 'lucide-react';
import { NavSection } from '../../types';

interface LandingPageProps {
  onNavigate: (section: NavSection) => void;
  onOpenLogin: () => void;
}

export function LandingPage({ onNavigate, onOpenLogin }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-brand-500/30 selection:text-brand-200 relative overflow-hidden flex flex-col justify-between">
      {/* Background Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[350px] bg-gradient-to-b from-brand-500/10 via-cyan-500/5 to-transparent blur-3xl pointer-events-none rounded-full" />

      {/* Top Header Navigation */}
      <header className="sticky top-0 z-40 border-b border-slate-900 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onNavigate('landing')}>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-cyan-400 p-0.5 shadow-md shadow-brand-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[6px] flex items-center justify-center">
                <ShieldCheck className="w-4 h-4 text-brand-400" />
              </div>
            </div>
            <span className="font-extrabold text-base text-white tracking-tight">
              Aegis <span className="text-brand-400">AI</span>
            </span>
          </div>

          <div className="hidden md:flex items-center space-x-6 text-xs font-medium text-slate-400">
            <button onClick={() => onNavigate('landing')} className="text-white font-semibold">Home</button>
            <button onClick={() => onNavigate('workspace')} className="hover:text-white transition-colors">Workspace</button>
            <button onClick={() => onNavigate('repository')} className="hover:text-white transition-colors">Regulations</button>
            <button onClick={() => onNavigate('graph')} className="hover:text-white transition-colors">Knowledge Graph</button>
            <button onClick={() => onNavigate('copilot')} className="hover:text-white transition-colors">Copilot</button>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => onNavigate('workspace')}
              className="px-3.5 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-850 rounded-lg border border-slate-800 transition-all"
            >
              Launch App
            </button>
            <button
              onClick={onOpenLogin}
              className="px-3.5 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-500 rounded-lg shadow-md shadow-brand-600/20 transition-all flex items-center gap-1.5"
            >
              <Lock className="w-3 h-3" />
              <span>Sign In</span>
            </button>
          </div>
        </div>
      </header>

      {/* MINIMAL HERO SECTION */}
      <main className="max-w-5xl mx-auto px-6 pt-16 pb-20 my-auto text-center space-y-8 relative z-10">
        
        {/* Minimal Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-medium text-slate-300">
          <Sparkles className="w-3.5 h-3.5 text-brand-400" />
          <span>Enterprise Regulatory OS</span>
        </div>

        {/* Minimal Headline */}
        <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          Autonomous Regulatory Intelligence & <br />
          <span className="bg-gradient-to-r from-brand-400 via-cyan-300 to-indigo-400 bg-clip-text text-transparent">
            8-Hop Impact Lineage
          </span>
        </h1>

        {/* Minimal Subheadline */}
        <p className="max-w-2xl mx-auto text-xs sm:text-sm text-slate-400 leading-relaxed">
          Automate statutory clause extraction across RBI, SEC, SEBI, and CERT-In mandates with deterministic zero-hallucination accuracy.
        </p>

        {/* Minimal Action Buttons */}
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => onNavigate('workspace')}
            className="px-6 py-2.5 rounded-lg font-semibold text-xs text-white bg-brand-600 hover:bg-brand-500 shadow-lg shadow-brand-600/20 transition-all flex items-center gap-2"
          >
            <span>Launch App</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => onNavigate('graph')}
            className="px-6 py-2.5 rounded-lg font-semibold text-xs text-slate-300 hover:text-white bg-slate-900 hover:bg-slate-850 border border-slate-800 transition-all flex items-center gap-2"
          >
            <GitFork className="w-3.5 h-3.5 text-cyan-400" />
            <span>Explore Knowledge Graph</span>
          </button>
        </div>

        {/* Minimal Stats */}
        <div className="pt-10 grid grid-cols-3 gap-4 max-w-xl mx-auto border-t border-slate-900">
          <div className="space-y-0.5">
            <div className="text-xl font-bold text-white font-mono">8-Hop</div>
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Impact Lineage</div>
          </div>
          <div className="space-y-0.5">
            <div className="text-xl font-bold text-cyan-400 font-mono">99.8%</div>
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Grounding Score</div>
          </div>
          <div className="space-y-0.5">
            <div className="text-xl font-bold text-emerald-400 font-mono">Zero</div>
            <div className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">Hallucination</div>
          </div>
        </div>

        {/* Minimal Feature Cards Grid */}
        <div className="pt-8 grid grid-cols-1 md:grid-cols-3 gap-4 text-left">
          
          <div
            onClick={() => onNavigate('graph')}
            className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-brand-500/40 transition-all space-y-2 cursor-pointer group"
          >
            <GitFork className="w-5 h-5 text-brand-400 group-hover:scale-110 transition-transform" />
            <h3 className="text-xs font-bold text-white">Statutory Lineage</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Traces regulatory amendments directly to internal controls (`CTRL-*`) and IT systems.
            </p>
          </div>

          <div
            onClick={() => onNavigate('repository')}
            className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-cyan-500/40 transition-all space-y-2 cursor-pointer group"
          >
            <Activity className="w-5 h-5 text-cyan-400 group-hover:scale-110 transition-transform" />
            <h3 className="text-xs font-bold text-white">Live Source Verification</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Compares stored clauses against live government web pages to detect stealth drift.
            </p>
          </div>

          <div
            onClick={() => onNavigate('copilot')}
            className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-purple-500/40 transition-all space-y-2 cursor-pointer group"
          >
            <Bot className="w-5 h-5 text-purple-400 group-hover:scale-110 transition-transform" />
            <h3 className="text-xs font-bold text-white">RAG Copilot</h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Answers regulatory queries with verbatim statutory paragraph citations.
            </p>
          </div>

        </div>

      </main>

      {/* MINIMAL FOOTER */}
      <footer className="border-t border-slate-900 py-6 text-center text-[11px] text-slate-400">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
            <span className="font-bold text-slate-300">Aegis AI</span>
          </div>
          <div>© 2026 Aegis AI • Minimal Enterprise OS</div>
        </div>
      </footer>
    </div>
  );
}
