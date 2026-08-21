import React, { useState, useEffect, useCallback } from 'react';
import {
  Building2,
  Sparkles,
  Loader2,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  X,
} from 'lucide-react';
import { ServiceAPI } from '../../services/api';
import { FactReviewConsole } from './FactReviewConsole';

export interface OrganizationDiscoveryPageProps {
  mode?: 'initial' | 'rediscovery';
  initialWebsite?: string;
  orgStatus?: 'SETUP_REQUIRED' | 'DISCOVERING' | 'REVIEW_PENDING';
  onComplete: () => Promise<void>;
  onSetupManually?: () => void;
  onCancel?: () => void;
}

/**
 * Normalizes and validates user-entered company website URLs.
 * Handles missing protocol (auto-adds https://) and validates domain format.
 */
function validateAndNormalizeUrl(rawInput: string): { valid: boolean; normalized: string; error?: string } {
  let trimmed = rawInput.trim();
  if (!trimmed) {
    return { valid: false, normalized: '', error: 'Please enter your company website address.' };
  }

  // Auto-prefix https:// if protocol is omitted
  if (!/^https?:\/\//i.test(trimmed)) {
    trimmed = 'https://' + trimmed;
  }

  try {
    const parsed = new URL(trimmed);
    // Must have a valid hostname with at least one dot (e.g. example.com)
    if (!parsed.hostname || !parsed.hostname.includes('.') || parsed.hostname.endsWith('.')) {
      return { valid: false, normalized: '', error: 'Please enter a valid domain address (e.g. https://www.example.com).' };
    }
    // Remove trailing slash for consistency
    const normalized = parsed.origin + parsed.pathname.replace(/\/+$/, '') + parsed.search;
    return { valid: true, normalized };
  } catch {
    return { valid: false, normalized: '', error: 'Please enter a valid website URL.' };
  }
}

export const OrganizationDiscoveryPage: React.FC<OrganizationDiscoveryPageProps> = ({
  mode = 'initial',
  initialWebsite = '',
  orgStatus: initialOrgStatus = 'SETUP_REQUIRED',
  onComplete,
  onSetupManually,
  onCancel,
}) => {
  const [currentStatus, setCurrentStatus] = useState<'SETUP_REQUIRED' | 'DISCOVERING' | 'REVIEW_PENDING'>(initialOrgStatus);
  const [website, setWebsite] = useState(mode === 'rediscovery' ? initialWebsite : '');
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [crawlError, setCrawlError] = useState<{ title: string; message: string; reason?: string } | null>(null);
  const [isCheckingUpdates, setIsCheckingUpdates] = useState(false);

  // Sync prop changes
  useEffect(() => {
    if (initialOrgStatus) {
      setCurrentStatus(initialOrgStatus);
    }
  }, [initialOrgStatus]);

  const checkDiscoveryStatus = useCallback(async () => {
    try {
      setIsCheckingUpdates(true);
      const statusRes = await ServiceAPI.getDiscoveryStatus();
      if (statusRes.discovery_status === 'REVIEW_PENDING') {
        setCurrentStatus('REVIEW_PENDING');
      } else if (statusRes.discovery_status === 'CONFIRMED') {
        await onComplete();
      } else if (statusRes.discovery_status === 'FAILED' || statusRes.discovery_status === 'UNINITIALIZED') {
        setCurrentStatus('SETUP_REQUIRED');
        if (statusRes.discovery_status === 'FAILED') {
          setCrawlError({
            title: "We couldn't learn enough about this website",
            message: "We were able to reach the website, but there wasn't enough publicly accessible information for us to build a reliable organization profile."
          });
        }
      }
    } catch (err) {
      console.warn('Status check failed:', err);
    } finally {
      setIsCheckingUpdates(false);
    }
  }, [onComplete]);

  useEffect(() => {
    if (currentStatus !== 'DISCOVERING') return;

    const interval = setInterval(() => {
      checkDiscoveryStatus();
    }, 4000);

    return () => clearInterval(interval);
  }, [currentStatus, checkDiscoveryStatus]);

  // ---------------------------------------------------------------------------
  // Handle Discovery Start (Explicit User Action)
  // ---------------------------------------------------------------------------
  const handleStartDiscovery = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);
    setCrawlError(null);

    const validation = validateAndNormalizeUrl(website);
    if (!validation.valid) {
      setError(validation.error || 'Please enter a valid website URL.');
      return;
    }

    try {
      setIsStarting(true);
      const res = await ServiceAPI.startDiscovery(validation.normalized);

      if (res.status === 'SUCCESS') {
        // Discovery crawl + extraction succeeded -> move to Review
        setCurrentStatus('REVIEW_PENDING');
      } else {
        throw new Error('Discovery failed to initiate.');
      }
    } catch (err: any) {
      console.error('Discovery initiation failed:', err);
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object' && detail?.message) {
        setCrawlError({
          title: "We couldn't learn enough about this website",
          message: "We were able to reach the website, but there wasn't enough publicly accessible information for us to build a reliable organization profile.",
          reason: detail.reason
        });
      } else if (typeof detail === 'string' && detail !== 'Not Found') {
        setCrawlError({
          title: "We couldn't learn enough about this website",
          message: detail
        });
      } else {
        setCrawlError({
          title: "We couldn't learn enough about this website",
          message: "We were able to reach the website, but there wasn't enough publicly accessible information for us to build a reliable organization profile."
        });
      }
    } finally {
      setIsStarting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // View 1: REVIEW_PENDING — Human Review of Discovered Findings
  // ---------------------------------------------------------------------------
  if (currentStatus === 'REVIEW_PENDING') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <header className="border-b border-slate-800/80 bg-slate-900/40 backdrop-blur-md px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-cyan-400 p-0.5 shadow-md shadow-brand-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[6px] flex items-center justify-center">
                <ShieldCheck className="w-4 h-4 text-brand-400" />
              </div>
            </div>
            <div>
              <span className="font-extrabold text-sm text-white tracking-tight">
                Aegis <span className="text-brand-400">AI</span>
              </span>
              <span className="text-xs text-slate-500 ml-2 border-l border-slate-700 pl-2">
                Review Discovered Information
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            Review Pending
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <FactReviewConsole
            onFinalize={async () => {
              await onComplete();
            }}
          />
        </main>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // View 2: DISCOVERING — Discovery in Progress
  // ---------------------------------------------------------------------------
  if (currentStatus === 'DISCOVERING') {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <header className="border-b border-slate-800/80 bg-slate-900/40 backdrop-blur-md px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-cyan-400 p-0.5 shadow-md shadow-brand-500/20">
              <div className="w-full h-full bg-slate-950 rounded-[6px] flex items-center justify-center">
                <ShieldCheck className="w-4 h-4 text-brand-400" />
              </div>
            </div>
            <span className="font-extrabold text-sm text-white tracking-tight">
              Aegis <span className="text-brand-400">AI</span>
            </span>
          </div>
        </header>

        <main className="flex-1 flex items-center justify-center p-6">
          <div className="glass-panel rounded-2xl border border-slate-800 w-full max-w-lg p-10 flex flex-col items-center gap-6 text-center shadow-2xl">
            <div className="relative w-20 h-20">
              <div className="absolute inset-0 border-4 border-slate-800 rounded-full" />
              <div className="absolute inset-0 border-4 border-brand-500 rounded-full border-t-transparent animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center text-brand-400">
                <Sparkles className="w-8 h-8 animate-pulse" />
              </div>
            </div>

            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Discovery in Progress
              </h1>
              <p className="text-sm text-slate-400 max-w-sm mx-auto leading-relaxed">
                We're reviewing publicly available information about your organization. You can leave this page and return later.
              </p>
            </div>

            <div className="w-full bg-slate-900/60 rounded-xl p-4 border border-slate-800/80 text-xs text-slate-400 text-left space-y-2">
              <div className="flex items-center gap-2 text-slate-300 font-medium">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />
                Analyzing public corporate pages...
              </div>
              <p className="text-[11px] text-slate-500">
                When complete, you'll review and confirm all candidate facts before they become part of your organization's trusted context.
              </p>
            </div>

            <div className="pt-2 flex flex-col sm:flex-row gap-3 w-full">
              <button
                type="button"
                onClick={checkDiscoveryStatus}
                disabled={isCheckingUpdates}
                className="btn-secondary flex-1 py-2.5 text-xs flex items-center justify-center gap-2"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isCheckingUpdates ? 'animate-spin' : ''}`} />
                {isCheckingUpdates ? 'Checking...' : 'Check for Updates'}
              </button>
              <button
                type="button"
                onClick={() => { setCurrentStatus('SETUP_REQUIRED'); setCrawlError(null); }}
                className="text-xs text-slate-400 hover:text-slate-200 px-3 py-2.5 transition-colors"
              >
                Change website
              </button>
              {onSetupManually && (
                <button
                  type="button"
                  onClick={onSetupManually}
                  className="text-xs text-slate-400 hover:text-white px-3 py-2.5 transition-colors"
                >
                  Set up manually
                </button>
              )}
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // View 3: SETUP_REQUIRED / WEBSITE ENTRY (Canonical Entry Screen)
  // Used for both First-time Onboarding & Discover Again
  // ---------------------------------------------------------------------------
  const isRediscovery = mode === 'rediscovery';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-brand-500/30 selection:text-brand-200">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-cyan-400 p-0.5 shadow-md shadow-brand-500/20">
            <div className="w-full h-full bg-slate-950 rounded-[6px] flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-brand-400" />
            </div>
          </div>
          <span className="font-extrabold text-base text-white tracking-tight">
            Aegis <span className="text-brand-400">AI</span>
          </span>
          {isRediscovery && (
            <span className="text-xs text-slate-400 border-l border-slate-800 pl-3">
              Re-Discovery
            </span>
          )}
        </div>

        {isRediscovery ? (
          <button
            type="button"
            onClick={onCancel}
            className="text-xs font-semibold text-slate-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            <span>Cancel</span>
          </button>
        ) : onSetupManually ? (
          <button
            type="button"
            onClick={onSetupManually}
            className="text-xs font-semibold text-slate-400 hover:text-white transition-colors"
          >
            Manual Setup →
          </button>
        ) : null}
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-6 relative">
        {/* Background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-gradient-to-b from-brand-500/10 via-cyan-500/5 to-transparent blur-3xl pointer-events-none rounded-full" />

        <div className="glass-panel rounded-2xl border border-slate-800 w-full max-w-lg p-8 sm:p-10 flex flex-col relative shadow-2xl z-10 space-y-6">
          {/* Header */}
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/20 text-xs font-medium text-brand-300">
              <Sparkles className="w-3.5 h-3.5 text-brand-400" />
              <span>{isRediscovery ? 'Update Context' : 'Automated Setup'}</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {isRediscovery ? 'Discover Organization Again' : 'Discover Your Organization'}
            </h1>

            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              {isRediscovery
                ? "Enter the website you'd like ReguGuard to review. Your existing confirmed organization information will remain unchanged until new findings are reviewed."
                : "Start by entering your company's website. We'll review publicly available information to build an initial organization profile. You'll review everything before it becomes part of your organization's trusted context."}
            </p>
          </div>

          {/* Simple validation error */}
          {error && (
            <div className="p-4 bg-rose-950/30 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-300 text-xs leading-relaxed">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <p>{error}</p>
            </div>
          )}

          {/* Structured public-web discovery fallback experience */}
          {crawlError && (
            <div className="p-6 bg-slate-900/90 border border-amber-500/30 rounded-2xl flex flex-col gap-4 text-left shadow-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-amber-400" />
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-white">{crawlError.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{crawlError.message}</p>
                </div>
              </div>

              <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800/80 space-y-2">
                <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">What we checked</div>
                <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                  <div className="flex items-center gap-1.5 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span className="text-slate-300">Website address</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span className="text-slate-300">Public pages</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span className="text-slate-300">Available navigation</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-amber-400">
                    <div className="w-3.5 h-3.5 rounded-full border-2 border-amber-400 shrink-0" />
                    <span className="text-slate-300">Enough organization facts</span>
                  </div>
                </div>
              </div>

              <div className="pt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleStartDiscovery()}
                  disabled={isStarting}
                  className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-xs font-semibold shadow-md transition-all flex items-center gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Try Again</span>
                </button>
                <button
                  type="button"
                  onClick={() => { setCrawlError(null); setWebsite(''); }}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-semibold transition-all"
                >
                  Use a Different Website
                </button>
                {onSetupManually && (
                  <button
                    type="button"
                    onClick={onSetupManually}
                    className="px-4 py-2 text-xs text-slate-400 hover:text-white transition-colors ml-auto"
                  >
                    Set Up Manually
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleStartDiscovery} className="space-y-5">
            <div className="space-y-2">
              <label htmlFor="company-website" className="text-xs font-semibold text-slate-300 block">
                Company website
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Building2 className="h-4 w-4" />
                </div>
                <input
                  id="company-website"
                  type="text"
                  required
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://www.example.com"
                  disabled={isStarting}
                  className="w-full bg-slate-900/80 border border-slate-700/80 rounded-xl py-3 pl-10 pr-4 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all disabled:opacity-50"
                />
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                {isRediscovery
                  ? 'We will extract updated findings for your review. No data will be overwritten automatically.'
                  : "You'll review everything we find before it becomes part of your organization profile."}
              </p>
            </div>

            <div className="pt-2 flex flex-col gap-3">
              <button
                type="submit"
                disabled={isStarting || !website.trim()}
                className="w-full bg-brand-600 hover:bg-brand-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-semibold text-xs sm:text-sm py-3 px-4 rounded-xl shadow-lg shadow-brand-600/20 transition-all flex items-center justify-center gap-2"
              >
                {isStarting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Initiating Discovery...</span>
                  </>
                ) : (
                  <>
                    <span>{isRediscovery ? 'Start New Discovery' : 'Start Discovery'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              {isRediscovery ? (
                <button
                  type="button"
                  onClick={onCancel}
                  disabled={isStarting}
                  className="w-full bg-transparent hover:bg-slate-900/80 text-slate-400 hover:text-slate-200 font-medium py-2.5 px-4 rounded-xl transition-colors text-xs"
                >
                  Cancel
                </button>
              ) : onSetupManually ? (
                <button
                  type="button"
                  onClick={onSetupManually}
                  disabled={isStarting}
                  className="w-full bg-transparent hover:bg-slate-900/80 text-slate-400 hover:text-slate-200 font-medium py-2.5 px-4 rounded-xl transition-colors text-xs"
                >
                  Set up manually
                </button>
              ) : null}
            </div>
          </form>
        </div>
      </main>
    </div>
  );
};
