import React, { useState } from 'react';
import { X, ArrowRight, ShieldCheck, GitBranch, Bot, CheckCircle2, Sparkles, HelpCircle } from 'lucide-react';

interface GuidedTourModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateSection: (section: any) => void;
}

export const GuidedTourModal: React.FC<GuidedTourModalProps> = ({
  isOpen,
  onClose,
  onNavigateSection,
}) => {
  const [step, setStep] = useState(0);

  if (!isOpen) return null;

  const TOUR_STEPS = [
    {
      title: 'Welcome to ReguGuard AI',
      icon: Sparkles,
      color: 'text-brand-400',
      badge: 'Step 1 of 4: Platform Overview',
      description:
        'ReguGuard AI automates regulatory change management for enterprise banks and financial institutions. It continuously ingests statutory circulars (RBI, SEC), builds knowledge graphs, and enforces dual-control compliance sign-offs.',
      actionLabel: 'Explore Morning Briefing',
      targetSection: 'workspace',
    },
    {
      title: '8-Hop Enterprise Knowledge Graph',
      icon: GitBranch,
      color: 'text-cyan-400',
      badge: 'Step 2 of 4: Impact Blast Radius',
      description:
        'Instead of guessing which IT systems break when a new regulation is issued, the Knowledge Graph automatically maps: Regulation ➔ Section ➔ Requirement ➔ Control ➔ Policy ➔ Department ➔ Core Banking App.',
      actionLabel: 'View Interactive Graph Canvas',
      targetSection: 'graph',
    },
    {
      title: '4-Eyes Dual Control Sign-offs',
      icon: ShieldCheck,
      color: 'text-indigo-400',
      badge: 'Step 3 of 4: Governance Sign-off',
      description:
        'Prevents compliance failures by requiring dual-control verification (Compliance Officer + General Counsel). Approvals generate immutable cryptographic signature hashes (SIG-4EYES-XXXX) logged to the SOC2 audit ledger.',
      actionLabel: 'Open Reviews & Sign-offs Console',
      targetSection: 'reviews',
    },
    {
      title: 'Zero-Hallucination AI Copilot',
      icon: Bot,
      color: 'text-purple-400',
      badge: 'Step 4 of 4: Grounded Statutory AI',
      description:
        'Ask statutory compliance questions in plain English. The RAG pipeline retrieves exact statutory clauses (e.g. RBI Section 4.1) and provides 98%+ confidence answers with grounded citations.',
      actionLabel: 'Test AI Copilot',
      targetSection: 'copilot',
    },
  ];

  const current = TOUR_STEPS[step];
  const Icon = current.icon;

  const handleNext = () => {
    onNavigateSection(current.targetSection);
    if (step < TOUR_STEPS.length - 1) {
      setStep(step + 1);
    } else {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="glass-panel p-6 rounded-2xl border border-brand-500/30 w-full max-w-lg space-y-5 shadow-2xl relative">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <span className="px-2.5 py-0.5 text-xs font-bold bg-brand-500/20 text-brand-300 rounded-full border border-brand-500/30 flex items-center gap-1">
            <HelpCircle className="w-3.5 h-3.5" /> {current.badge}
          </span>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div className="flex items-center space-x-3">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
              <Icon className={`w-6 h-6 ${current.color}`} />
            </div>
            <h2 className="text-lg font-extrabold text-white">{current.title}</h2>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-4 rounded-xl border border-slate-800">
            {current.description}
          </p>
        </div>

        {/* Stepper Progress Indicator */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center space-x-1.5">
            {TOUR_STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all ${
                  i === step ? 'w-6 bg-brand-500' : 'w-2 bg-slate-800'
                }`}
              />
            ))}
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="px-3.5 py-2 text-xs font-semibold text-slate-400 hover:text-white"
            >
              Skip Tour
            </button>
            <button
              onClick={handleNext}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-brand-600/30 transition-all flex items-center gap-1.5"
            >
              <span>{current.actionLabel}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
