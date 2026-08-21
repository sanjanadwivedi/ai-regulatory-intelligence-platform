import React, { useState } from 'react';
import { X, ArrowRight, ShieldCheck, GitBranch, Bot, CheckCircle2, Sparkles, HelpCircle, Building2, FileText } from 'lucide-react';

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
      title: '1. Organization Discovery',
      icon: Building2,
      color: 'text-amber-400',
      badge: 'Step 1 of 8: Profile Configuration',
      description: 'Define your Enterprise Profile. ReguGuard AI automatically identifies key business activities, sectors, and jurisdictions to build your organizational context.',
      actionLabel: 'Setup Enterprise Profile',
      targetSection: 'organization-discovery',
    },
    {
      title: '2. Regulatory Repository',
      icon: Sparkles,
      color: 'text-brand-400',
      badge: 'Step 2 of 8: AI Ingestion',
      description: 'Ingest and monitor real-time regulatory signals from global authorities. Documents are processed to detect entities, deadlines, and requirements.',
      actionLabel: 'Explore Repository',
      targetSection: 'repository',
    },
    {
      title: '3. Legal Applicability',
      icon: GitBranch,
      color: 'text-cyan-400',
      badge: 'Step 3 of 8: Impact Assessment',
      description: 'The AI matches your Enterprise Profile against the regulatory rules to determine exactly which statutes apply to your organization.',
      actionLabel: 'View Applicability',
      targetSection: 'workspace',
    },
    {
      title: '4. Statutory Obligations',
      icon: ShieldCheck,
      color: 'text-indigo-400',
      badge: 'Step 4 of 8: Extraction',
      description: 'Extract actionable requirements and map them to your internal controls, creating a deterministic Knowledge Graph from Law to Code.',
      actionLabel: 'Review Obligations',
      targetSection: 'workspace',
    },
    {
      title: '5. Operational Tasks',
      icon: CheckCircle2,
      color: 'text-emerald-400',
      badge: 'Step 5 of 8: Task Instantiation',
      description: 'Generate trackable operational tasks from active statutory obligations. Distinguish clearly between internal deadlines and legal mandates.',
      actionLabel: 'Manage Tasks',
      targetSection: 'actions',
    },
    {
      title: '6. Task Execution & Evidence',
      icon: FileText,
      color: 'text-purple-400',
      badge: 'Step 6 of 8: Action Center',
      description: 'Perform work, record trigger events, attach documentation, and secure 4-eyes dual-control sign-offs for critical compliance actions.',
      actionLabel: 'Execute Tasks',
      targetSection: 'actions',
    },
    {
      title: '7. Evidence & Audit Package',
      icon: ShieldCheck,
      color: 'text-brand-400',
      badge: 'Step 7 of 8: Cryptographic Audit',
      description: 'Generate immutable snapshots of your compliance posture, linking statutory requirements directly to executed tasks and evidence files.',
      actionLabel: 'Generate Audit Package',
      targetSection: 'intelligence',
    },
    {
      title: '8. Ambient AI Copilot',
      icon: Bot,
      color: 'text-rose-400',
      badge: 'Step 8 of 8: Continuous Intelligence',
      description: 'Ask grounded questions in plain English. The AI Copilot accesses your entire 3-Layer architecture to explain reasoning and trace provenance.',
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
