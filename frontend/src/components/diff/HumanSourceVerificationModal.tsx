import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, X, Sparkles, Check, Link as LinkIcon, Loader2 } from 'lucide-react';
import { ServiceAPI } from '../../services/api';
import { Regulation } from '../../types';

interface Props {
  regulation: Regulation;
  onClose: () => void;
  onVerified: () => void;
}

export const HumanSourceVerificationModal: React.FC<Props> = ({ regulation, onClose, onVerified }) => {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    
    setLoading(true);
    setResult(null);
    try {
      const res = await ServiceAPI.verifyHumanSource(regulation.id, url);
      setResult(res);
      if (res.valid) {
        setTimeout(() => {
          onVerified();
        }, 2000);
      }
    } catch (err: any) {
      setResult({
        valid: false,
        reason: err?.response?.data?.detail || err.message || "Failed to verify source",
        checks: {}
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] bg-slate-950/90 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-xl w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-xl text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Provide Official Source</h2>
            <p className="text-sm text-slate-400">Strict deterministic verification required.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-bold text-slate-300 mb-2">
              Official Document URL
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <LinkIcon className="h-5 w-5 text-slate-500" />
              </div>
              <input
                type="url"
                required
                disabled={loading || result?.valid}
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://rbidocs.rbi.org.in/..."
                className="w-full bg-slate-950 border border-slate-700 rounded-xl py-3 pl-11 pr-4 text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Must be the exact official source for: <span className="font-mono text-slate-300">{regulation.doc_number || regulation.title}</span>
            </p>
          </div>

          {!result && (
            <div className="pt-4 flex justify-end">
              <button
                type="submit"
                disabled={loading || !url}
                className="px-6 py-3 bg-brand-600 hover:bg-brand-500 text-white font-bold rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ShieldCheck className="w-5 h-5" />}
                <span>Verify Source Identity</span>
              </button>
            </div>
          )}
        </form>

        {result && (
          <div className="mt-6 space-y-4">
            <div className={`p-4 rounded-xl border ${result.valid ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-rose-500/10 border-rose-500/30 text-rose-300'}`}>
              <div className="flex items-center gap-2 mb-2">
                {result.valid ? <ShieldCheck className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
                <h3 className="font-bold">{result.valid ? 'Verification Successful' : 'Verification Failed'}</h3>
              </div>
              <p className="text-sm opacity-90">{result.reason}</p>
            </div>

            {result.checks && Object.keys(result.checks).length > 0 && (
              <div className="bg-slate-950 rounded-xl p-4 border border-slate-800">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Deterministic Checks</h4>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(result.checks).map(([key, passed]: any) => (
                    <div key={key} className="flex items-center gap-2 text-sm">
                      {passed ? (
                        <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                      ) : (
                        <X className="w-4 h-4 text-rose-400 shrink-0" />
                      )}
                      <span className={passed ? 'text-slate-300' : 'text-slate-500 line-through'}>
                        {key.replace('_', ' ')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {result.valid && (
              <p className="text-sm text-emerald-400 text-center animate-pulse pt-2">
                Reloading live source diff...
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
