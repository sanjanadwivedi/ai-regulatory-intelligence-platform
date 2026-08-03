import React, { useState } from 'react';
import { Building2, Globe, ShieldCheck, Sparkles, X, ArrowRight, Check } from 'lucide-react';

interface EnterpriseSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentProfile?: any;
  onSaveProfile: (profileData: {
    organization_name: string;
    industry_sector: string;
    departments: string[];
    country?: string;
  }) => Promise<any>;
}

export const INDUSTRIES = [
  {
    id: 'Technology & Cloud Security (SOC2 / GDPR)',
    name: 'Technology & Cloud Security (SOC2 / GDPR)',
    depts: ['Information Security (CISO)', 'Data Protection Office (DPO)', 'DevOps Infrastructure', 'Legal Counsel'],
    desc: 'Cloud Infrastructure, Encryption, SOC2 Audit, CVE Patching & Incident Reporting Rules'
  },
  {
    id: 'Banking & Financial Services',
    name: 'Banking & Financial Services (RBI / EBA)',
    depts: ['Retail Banking Ops', 'AML & CDD Compliance', 'IT Infrastructure & Security', 'Legal Counsel'],
    desc: 'KYC, Anti-Money Laundering (AML), V-CIP, Prudential Ratios & Banking Governance'
  },
  {
    id: 'Healthcare & Life Sciences',
    name: 'Healthcare & Life Sciences (HIPAA / FDA)',
    depts: ['Clinical Operations', 'Patient Data Governance (PHI)', 'Medical Device Compliance', 'Legal Counsel'],
    desc: 'HIPAA Patient Data Privacy, EHR Access Audit Logging & Clinical Regulations'
  },
  {
    id: 'Capital Markets & Securities',
    name: 'Capital Markets & Securities (SEC / FINRA)',
    depts: ['Trading & Market Surveillance', 'Equity Research Compliance', 'IT Infrastructure', 'Legal Counsel'],
    desc: 'SEC Algorithmic Trading Controls, Insider Trading Audits & Public Disclosure Rules'
  },
];

export const EnterpriseSetupModal: React.FC<EnterpriseSetupModalProps> = ({
  isOpen,
  onClose,
  currentProfile,
  onSaveProfile,
}) => {
  const [orgName, setOrgName] = useState(currentProfile?.organization_name || 'HDFC Bank Ltd');
  const [selectedIndustry, setSelectedIndustry] = useState(currentProfile?.industry_sector || 'Technology & Cloud Security (SOC2 / GDPR)');
  const [country, setCountry] = useState(currentProfile?.country || 'India');
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const currentObj = INDUSTRIES.find(i => i.id === selectedIndustry) || INDUSTRIES[0];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSaveProfile({
        organization_name: orgName,
        industry_sector: selectedIndustry,
        departments: currentObj.depts,
        country: country,
      });
      onClose();
    } catch (err) {
      console.error('Failed to save profile setup:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4">
      <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-brand-500/40 w-full max-w-2xl space-y-6 shadow-2xl relative animate-in fade-in zoom-in-95">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center text-brand-400 font-bold">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-white flex items-center gap-2">
                Enterprise Industry & Profile Setup <Sparkles className="w-4 h-4 text-brand-400" />
              </h2>
              <p className="text-xs text-slate-400">Step 1: Set your organization and industry sector to route relevant legal directives</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded-xl">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-slate-200 font-bold block">Organization / Company Name</label>
              <input
                type="text"
                required
                placeholder="e.g. HDFC Bank Ltd or Apex Tech Solutions"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500 font-semibold"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-slate-200 font-bold block">Country / Primary Jurisdiction</label>
              <input
                type="text"
                required
                placeholder="e.g. India, United States, Europe"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500 font-semibold"
              />
            </div>
          </div>

          {/* Industry Sector Selector Cards */}
          <div className="space-y-2">
            <label className="text-slate-200 font-bold block">Select Primary Industry Sector:</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {INDUSTRIES.map((ind) => {
                const isSelected = selectedIndustry === ind.id;
                return (
                  <div
                    key={ind.id}
                    onClick={() => setSelectedIndustry(ind.id)}
                    className={`p-4 rounded-2xl cursor-pointer border transition-all space-y-1.5 ${
                      isSelected
                        ? 'bg-gradient-to-r from-brand-600/30 to-brand-500/10 border-brand-500 text-white shadow-lg shadow-brand-600/20 scale-[1.02]'
                        : 'bg-slate-900/80 hover:bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-white">{ind.name}</span>
                      {isSelected && <Check className="w-4 h-4 text-emerald-400 font-bold" />}
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{ind.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Department Mapping Preview */}
          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              Auto-Mapped Internal Departments for {currentObj.name}:
            </span>
            <div className="flex flex-wrap gap-2">
              {currentObj.depts.map((d, i) => (
                <span key={i} className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-brand-300 text-[11px] font-semibold">
                  {d}
                </span>
              ))}
            </div>
          </div>

          {/* Footer Submit */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl bg-slate-900 text-slate-300 hover:text-white border border-slate-800 font-bold text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-6 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-extrabold text-xs shadow-lg shadow-brand-600/30 flex items-center gap-2 hover:scale-105 transition-all"
            >
              <span>{isSaving ? 'Configuring Profile...' : 'Save Profile & Load Directives'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
