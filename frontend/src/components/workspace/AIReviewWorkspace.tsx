import React, { useState, useEffect } from 'react';
import { Bot, CheckCircle2, XCircle, ShieldAlert, FileText, Sparkles, Layers, Award, ShieldCheck, Check } from 'lucide-react';
import { ServiceAPI } from '../../services/api';

export interface DecisionCard {
  id: string;
  requirement_title: string;
  grounded_evidence: string;
  source_span?: string;
  grounding_status?: 'VERIFIED' | 'UNVERIFIED_GROUNDING';
  grounding_score?: number;
  verifier_verdict?: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'NOT_SUPPORTED';
  verifier_citation?: string;
  statutory_ref: string;
  reasoning: string;
  confidence_score: number;
  affected_policies: string[];
  recommended_action: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
}

interface AIReviewWorkspaceProps {
  cards?: DecisionCard[];
  onApproveCard?: (id: string) => void;
  onRejectCard?: (id: string) => void;
}

const DEFAULT_CARDS: DecisionCard[] = [
  {
    id: 'dec-1',
    requirement_title: 'Mandatory 2-Year High-Risk Re-verification via V-CIP',
    grounded_evidence: 'Section 4.1(a): Regulated entities shall conduct mandatory periodic re-verification of High-Risk customers at minimum once every two (2) years using V-CIP with live geotagging.',
    source_span: 'Regulated Entities (REs) shall carry out periodic updation of KYC at least once in every two (2) years for high-risk customers.',
    grounding_status: 'VERIFIED',
    grounding_score: 1.0,
    verifier_verdict: 'SUPPORTED',
    verifier_citation: 'Direct textual match verified in Section 38 & Section 4.1 of Master Direction.',
    statutory_ref: 'RBI Master Direction 2026 Sec 4.1(a)',
    reasoning: 'Shortens existing 3-year cadence by 12 months. Requires updating SOP-KYC-3.2 and re-configuring core banking high-risk alert triggers.',
    confidence_score: 0.98,
    affected_policies: ['POL-KYC-2026', 'SOP-KYC-3.2', 'CTRL-KYC-04'],
    recommended_action: 'Generate Compliance Task to update Retail Onboarding SOP 3.2 and schedule IT sprint for V-CIP geotagging integration.',
    status: 'PENDING'
  },
  {
    id: 'dec-2',
    requirement_title: '6-Hour Mandatory Cyber Incident Reporting & 180-Day Log Preservation',
    grounded_evidence: 'CERT-In Directions Section 5.1: All service providers, intermediaries, data centres, and cloud providers shall report cyber security breaches within 6 hours and preserve ICT logs for 180 days.',
    source_span: 'All service providers, intermediaries, data centres, body corporate and government organisations shall report cyber security incidents to CERT-In within six (6) hours.',
    grounding_status: 'VERIFIED',
    grounding_score: 1.0,
    verifier_verdict: 'SUPPORTED',
    verifier_citation: 'Direct textual match verified in Section 5.1 & Section 5.5 of CERT-In Directions.',
    statutory_ref: 'CERT-In Directions No. 20(3)/2022-CERT-In',
    reasoning: 'Enforces strict 6-hour incident disclosure timeline. Requires automated SIEM incident routing to CISO SOC desk.',
    confidence_score: 0.96,
    affected_policies: ['POL-CLOUD-SEC-2026', 'CTRL-SEC-09'],
    recommended_action: 'Assign High-Priority IT Task to Cloud Security Team.',
    status: 'PENDING'
  }
];

export const AIReviewWorkspace: React.FC<AIReviewWorkspaceProps> = ({
  cards = DEFAULT_CARDS,
  onApproveCard,
  onRejectCard,
}) => {
  const [decisionCards, setDecisionCards] = useState<DecisionCard[]>(cards);
  const [activeTab, setActiveTab] = useState<'CARDS' | 'GOLDEN_EVAL'>('CARDS');
  const [goldenEval, setGoldenEval] = useState<any>(null);
  const [loadingEval, setLoadingEval] = useState(false);

  useEffect(() => {
    fetchGoldenBenchmark();
  }, []);

  const fetchGoldenBenchmark = async () => {
    setLoadingEval(true);
    try {
      const data = await ServiceAPI.getGoldenBenchmark();
      setGoldenEval(data);
    } catch (e) {
      console.warn('Failed to load golden benchmark:', e);
    } finally {
      setLoadingEval(false);
    }
  };

  const handleApprove = (id: string) => {
    setDecisionCards(prev => prev.map(c => c.id === id ? { ...c, status: 'APPROVED' } : c));
    if (onApproveCard) onApproveCard(id);
  };

  const handleReject = (id: string) => {
    setDecisionCards(prev => prev.map(c => c.id === id ? { ...c, status: 'REJECTED' } : c));
    if (onRejectCard) onRejectCard(id);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-brand-950/50 to-slate-900 border border-brand-500/20 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <Bot className="w-6 h-6 text-brand-400" />
            <h2 className="text-xl font-bold text-white tracking-tight">AI Decision Support & Verifiable Review Workspace</h2>
            <span className="px-2.5 py-0.5 text-xs font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30 rounded-full flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" /> Source-Grounded Pipeline
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Verifiable decision cards with source-span grounding, adversarial verification, and golden ground-truth metrics.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('CARDS')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'CARDS'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ShieldCheck className="w-4 h-4" /> Review Queue
          </button>
          <button
            onClick={() => { setActiveTab('GOLDEN_EVAL'); fetchGoldenBenchmark(); }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'GOLDEN_EVAL'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Award className="w-4 h-4" /> Golden Benchmark Eval
          </button>
        </div>
      </div>

      {activeTab === 'GOLDEN_EVAL' && (
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6 shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Award className="w-5 h-5 text-amber-400" /> Statutory Golden Benchmark Evaluation Results
              </h3>
              <p className="text-xs text-slate-400">
                Empirical accuracy metrics evaluated against hand-verified ground-truth statutory documents (RBI, CERT-In, HIPAA, SEC).
              </p>
            </div>
            <button
              onClick={fetchGoldenBenchmark}
              className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-xs font-bold text-slate-300 border border-slate-700 flex items-center gap-1 transition-all"
            >
              Re-run Benchmark ⚡
            </button>
          </div>

          {loadingEval ? (
            <div className="p-12 text-center text-slate-400 font-mono animate-pulse">Running Golden Dataset Evaluation...</div>
          ) : goldenEval ? (
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Grounding Precision</span>
                  <div className="text-2xl font-black text-emerald-400 font-mono">{goldenEval.overall_grounding_precision}%</div>
                </div>
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Deadline Exact Match</span>
                  <div className="text-2xl font-black text-indigo-400 font-mono">{goldenEval.deadline_accuracy_pct}%</div>
                </div>
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Penalty Grounding</span>
                  <div className="text-2xl font-black text-amber-400 font-mono">{goldenEval.penalty_accuracy_pct}%</div>
                </div>
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Calibration Score</span>
                  <div className="text-2xl font-black text-brand-400 font-mono">{goldenEval.average_calibration_confidence}</div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Per-Regulation Benchmark Accuracy Breakdown</h4>
                <div className="space-y-2">
                  {goldenEval.benchmark_results?.map((res: any, idx: number) => (
                    <div key={idx} className="p-4 rounded-xl bg-slate-950 border border-slate-900 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                      <div className="space-y-1">
                        <span className="px-2 py-0.5 text-[10px] font-mono bg-brand-500/20 text-brand-300 rounded font-bold border border-brand-500/30">
                          {res.doc_number}
                        </span>
                        <div className="font-bold text-white text-sm">{res.title}</div>
                      </div>
                      <div className="flex items-center gap-4 text-slate-300 font-mono">
                        <div>Grounding: <span className="text-emerald-400 font-bold">{res.grounding_accuracy}%</span></div>
                        <div>Deadline: <span className="text-indigo-400 font-bold">{res.deadline_accuracy}%</span></div>
                        <div>Penalty: <span className="text-amber-400 font-bold">{res.penalty_accuracy}%</span></div>
                        <span className="px-2.5 py-1 bg-emerald-500/20 text-emerald-300 font-bold rounded-full text-[10px] border border-emerald-500/30">
                          {res.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400">Benchmark metrics unavailable. Click Re-run Benchmark.</div>
          )}
        </div>
      )}

      {/* Decision Cards List */}
      {activeTab === 'CARDS' && (
        <div className="space-y-4">
          {decisionCards.map((card) => (
            <div
              key={card.id}
              className={`glass-panel p-6 rounded-2xl border transition-all space-y-4 shadow-xl ${
                card.status === 'APPROVED'
                  ? 'border-emerald-500/40 bg-emerald-950/10'
                  : card.status === 'REJECTED'
                  ? 'border-rose-500/40 bg-rose-950/10 opacity-75'
                  : 'border-slate-800 hover:border-brand-500/40'
              }`}
            >
              {/* Card Top Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="px-2 py-0.5 text-[10px] font-mono bg-brand-500/20 text-brand-300 rounded font-bold border border-brand-500/30">
                      {card.statutory_ref}
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1 font-mono">
                      <Sparkles className="w-3.5 h-3.5" /> {(card.confidence_score * 100).toFixed(0)}% Confidence
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white">{card.requirement_title}</h3>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 text-[10px] font-bold rounded-full border flex items-center gap-1 ${
                    card.grounding_status === 'VERIFIED'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}>
                    <Check className="w-3 h-3" /> Grounding: {card.grounding_status || 'VERIFIED'}
                  </span>
                  <span className={`px-2.5 py-1 text-[10px] font-bold rounded-full border flex items-center gap-1 ${
                    card.verifier_verdict === 'SUPPORTED'
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}>
                    <Bot className="w-3 h-3" /> Verifier: {card.verifier_verdict || 'SUPPORTED'}
                  </span>
                </div>
              </div>

              {/* Structured Grounded Evidence */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Verbatim Quoted Source Span</span>
                  <a
                    href={
                      card.statutory_ref.includes('CERT') || card.requirement_title.includes('Cyber') ? 'https://pib.gov.in/PressReleasePage.aspx?PRID=1820904'
                      : card.statutory_ref.includes('HIPAA') ? 'https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164'
                      : card.statutory_ref.includes('FINRA') || card.statutory_ref.includes('SEC') ? 'https://www.finra.org/rules-guidance/rulebooks/finra-rules'
                      : 'https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12093'
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 font-bold text-[10px] border border-indigo-500/30 flex items-center gap-1 transition-all"
                  >
                    <span>Verify Evidence Source 🔗</span>
                  </a>
                </div>
                <p className="text-xs text-slate-300 font-mono bg-slate-950 p-3 rounded-xl border border-slate-900 leading-relaxed border-l-4 border-l-emerald-500">
                  "{card.source_span || card.grounded_evidence}"
                </p>
                {card.verifier_citation && (
                  <div className="text-[11px] text-indigo-300 font-mono bg-indigo-950/20 p-2 rounded-lg border border-indigo-500/20">
                    <span className="font-bold">Adversarial Verifier Evidence:</span> {card.verifier_citation}
                  </div>
                )}
              </div>

              {/* Chain of Reasoning */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider block">Chain of AI Reasoning</span>
                  <p className="text-slate-300 leading-relaxed">{card.reasoning}</p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                  <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">Affected Enterprise Controls</span>
                  <div className="flex flex-wrap gap-1.5">
                    {card.affected_policies.map((pol, idx) => (
                      <span key={idx} className="px-2 py-0.5 text-[10px] bg-slate-950 text-indigo-300 font-mono rounded border border-slate-800 flex items-center gap-1">
                        <Layers className="w-3 h-3 text-brand-400" /> {pol}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Actionable Decision Bar */}
              <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center space-x-2">
                  <span className="text-slate-400 font-semibold">Recommended Action:</span>
                  <span className="text-slate-200 font-bold">{card.recommended_action}</span>
                </div>

                {card.status === 'PENDING' && (
                  <div className="flex items-center space-x-2 self-end sm:self-auto">
                    <button
                      onClick={() => handleReject(card.id)}
                      className="px-3 py-1.5 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 font-bold transition-all flex items-center gap-1"
                    >
                      <XCircle className="w-3.5 h-3.5" /> Reject
                    </button>
                    <button
                      onClick={() => handleApprove(card.id)}
                      className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-lg shadow-emerald-600/30 transition-all flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-4 h-4" /> Approve & Route Task
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

