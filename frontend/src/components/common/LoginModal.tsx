import React, { useState } from 'react';
import { ShieldCheck, Lock, Mail, Key, Sparkles, Loader2, CheckCircle2 } from 'lucide-react';
import { ServiceAPI } from '../../services/api';

interface LoginModalProps {
  isOpen: boolean;
  onSuccess: (userData: any) => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onSuccess }) => {
  const [email, setEmail] = useState('sanjana@hdfcbank.com');
  const [password, setPassword] = useState('secretpassword');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setIsLoading(true);
    setErrorMsg('');

    try {
      const data = await ServiceAPI.login(email, password);
      setIsLoading(false);
      onSuccess(data);
    } catch (err: any) {
      setIsLoading(false);
      setErrorMsg(err.response?.data?.detail || 'Authentication failed. Please check credentials.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
        {/* Glow effect */}
        <div className="absolute -top-12 -left-12 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-12 -right-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500/20 to-indigo-500/20 border border-emerald-500/30 text-emerald-400 mb-2 shadow-lg shadow-emerald-500/10">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-slate-100">Enterprise Authentication</h2>
          <p className="text-xs text-slate-400">
            Sign in to access your Regulatory Intelligence & Compliance Workspace
          </p>
        </div>

        {errorMsg && (
          <div className="p-3 text-xs rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-emerald-400" /> Enterprise Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="sanjana@hdfcbank.com"
              className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-emerald-400" /> Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2 transition-all"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Authenticating JWT...</span>
              </>
            ) : (
              <>
                <Lock className="w-4 h-4" />
                <span>Secure Sign In</span>
              </>
            )}
          </button>
        </form>

        <div className="pt-3 border-t border-slate-800 text-center">
          <span className="text-[11px] text-slate-500 flex items-center justify-center gap-1">
            <Sparkles className="w-3 h-3 text-emerald-400" /> Protected by OAuth2 & JWT HS256 Authentication
          </span>
        </div>
      </div>
    </div>
  );
};
