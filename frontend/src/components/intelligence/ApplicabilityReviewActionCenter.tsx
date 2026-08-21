import React, { useEffect, useState } from 'react';
import { ServiceAPI } from '../../services/api';
import { ShieldAlert, Loader2, CheckCircle, FileText, Link as LinkIcon, Send } from 'lucide-react';

interface ReviewItem {
  id: string;
  organization_id: string;
  regulation_id: string;
  assessment_id: string;
  criterion_id: string;
  status: string;
  question: string;
  reason: string;
  required_fact: string;
  requested_value_type: string;
  evidence_required: string;
  suggested_evidence_sources: string[] | null;
  assigned_role: string;
  priority: string;
}

export function ApplicabilityReviewActionCenter() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const [formData, setFormData] = useState<Record<string, any>>({});
  const [resultMessage, setResultMessage] = useState<{ id: string, status: string, message: string } | null>(null);

  const fetchReviews = async () => {
    try {
      const data = await ServiceAPI.getApplicabilityReviews({ status: 'OPEN' });
      const underReview = await ServiceAPI.getApplicabilityReviews({ status: 'UNDER_REVIEW' });
      setReviews([...data, ...underReview]);
    } catch (e) {
      console.error('Failed to fetch reviews', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  const handleInputChange = (id: string, field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [id]: {
        ...prev[id],
        [field]: value
      }
    }));
  };

  const handleResolve = async (id: string) => {
    const data = formData[id] || {};
    if (!data.evidence_fact_value || !data.evidence_type || !data.evidence_strength) {
      alert('Please fill out fact value, evidence type, and evidence strength.');
      return;
    }

    setResolvingId(id);
    try {
      const res = await ServiceAPI.resolveApplicabilityReview(id, {
        evidence_fact_value: data.evidence_fact_value,
        evidence_type: data.evidence_type,
        evidence_strength: data.evidence_strength,
        source_url: data.source_url || 'https://internal-compliance-record.local',
        known_state: data.known_state || 'TRUE',
      });
      setResultMessage({ id, status: res.status, message: res.message });
      if (res.status === 'RESOLVED') {
        setTimeout(() => {
          setReviews(prev => prev.filter(r => r.id !== id));
        }, 3000);
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to submit evidence');
    } finally {
      setResolvingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-brand-400" />
      </div>
    );
  }

  if (reviews.length === 0) {
    return null;
  }

  return (
    <div className="glass-panel p-6 rounded-2xl border border-amber-500/30 mt-8 mb-8">
      <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
        <ShieldAlert className="w-6 h-6 text-amber-400" />
        Applicability Reviews Action Center
      </h3>
      <p className="text-slate-400 text-sm mb-6">
        {reviews.length} items require evidence or human review. The engine could not deterministically establish applicability without these facts.
      </p>

      <div className="space-y-6">
        {reviews.map(item => (
          <div key={item.id} className="bg-slate-900/50 p-5 rounded-xl border border-slate-800">
            <div className="flex justify-between items-start mb-4">
              <div>
                <span className="inline-block px-2 py-1 bg-amber-500/10 text-amber-400 text-xs font-bold rounded mb-2">
                  {item.status.replace('_', ' ')}
                </span>
                <h4 className="text-white font-bold text-lg mb-1">{item.regulation_id}</h4>
                <p className="text-slate-400 text-sm">{item.reason}</p>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-500 font-mono">ID: {item.id.split('-')[0]}</span>
              </div>
            </div>

            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/50 mb-5">
              <p className="text-brand-300 font-medium text-sm mb-2">{item.question}</p>
              <div className="grid grid-cols-2 gap-4 text-xs text-slate-400 mt-3">
                <div>
                  <span className="block text-slate-500 uppercase tracking-wider mb-1">Missing Fact</span>
                  <span className="font-mono text-slate-300">{item.required_fact}</span>
                </div>
                <div>
                  <span className="block text-slate-500 uppercase tracking-wider mb-1">Required Evidence</span>
                  <span className="text-slate-300">{item.evidence_required || 'Documented evidence'}</span>
                </div>
              </div>
              {item.suggested_evidence_sources && item.suggested_evidence_sources.length > 0 && (
                <div className="mt-3 text-xs">
                  <span className="block text-slate-500 uppercase tracking-wider mb-1">Suggested Sources</span>
                  <ul className="list-disc pl-4 text-slate-400">
                    {item.suggested_evidence_sources.map((s, idx) => <li key={idx}>{s}</li>)}
                  </ul>
                </div>
              )}
            </div>

            {/* Form */}
            {resultMessage?.id === item.id ? (
              <div className={`p-4 rounded-lg border flex items-start gap-3 ${resultMessage.status === 'RESOLVED' ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}>
                {resultMessage.status === 'RESOLVED' ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <ShieldAlert className="w-5 h-5 flex-shrink-0" />}
                <div>
                  <p className="font-bold">{resultMessage.status}</p>
                  <p className="text-sm mt-1">{resultMessage.message}</p>
                </div>
              </div>
            ) : (
              <div className="bg-slate-800/30 p-4 rounded-lg border border-slate-700/50">
                <h5 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4" /> Provide Evidence
                </h5>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Fact Value ({item.requested_value_type || 'STRING'})</label>
                    {item.requested_value_type === 'BOOLEAN' ? (
                      <select
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
                        onChange={(e) => handleInputChange(item.id, 'evidence_fact_value', e.target.value)}
                        defaultValue=""
                      >
                        <option value="" disabled>Select True/False...</option>
                        <option value="true">True</option>
                        <option value="false">False</option>
                      </select>
                    ) : (
                      <input
                        type="text"
                        placeholder="Enter value..."
                        className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
                        onChange={(e) => handleInputChange(item.id, 'evidence_fact_value', e.target.value)}
                      />
                    )}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Evidence Type</label>
                    <select
                      className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
                      onChange={(e) => handleInputChange(item.id, 'evidence_type', e.target.value)}
                      defaultValue=""
                    >
                      <option value="" disabled>Select Type...</option>
                      <option value="ORGANIZATION_PROFILE">Organization Profile</option>
                      <option value="LICENSE">License</option>
                      <option value="CERTIFICATE">Certificate</option>
                      <option value="REGULATORY_REGISTRATION">Regulatory Registration</option>
                      <option value="POLICY_DOCUMENT">Policy Document</option>
                      <option value="CONTRACT">Contract</option>
                      <option value="SYSTEM_RECORD">System Record</option>
                      <option value="AUTHORITATIVE_EXTERNAL_SOURCE">Authoritative External Source</option>
                      <option value="USER_ATTESTATION">User Attestation</option>
                      <option value="OTHER">Other</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Evidence Strength</label>
                    <select
                      className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
                      onChange={(e) => handleInputChange(item.id, 'evidence_strength', e.target.value)}
                      defaultValue=""
                    >
                      <option value="" disabled>Select Strength...</option>
                      <option value="AUTHORITATIVE">AUTHORITATIVE</option>
                      <option value="DOCUMENTED">DOCUMENTED</option>
                      <option value="ATTESTED">ATTESTED</option>
                      <option value="INFERRED">INFERRED</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Source URL / Reference</label>
                    <div className="relative">
                      <LinkIcon className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                      <input
                        type="text"
                        placeholder="https://..."
                        className="w-full bg-slate-900 border border-slate-700 rounded-md pl-9 pr-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500"
                        onChange={(e) => handleInputChange(item.id, 'source_url', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    className="btn-primary py-2 px-4 flex items-center gap-2"
                    onClick={() => handleResolve(item.id)}
                    disabled={resolvingId === item.id}
                  >
                    {resolvingId === item.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    Submit Evidence
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
