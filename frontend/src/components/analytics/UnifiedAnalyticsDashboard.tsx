import React, { useEffect, useState } from 'react';
import { ServiceAPI } from '../../services/api';
import {
  OrganizationPostureResponse,
  RegulationPostureResponse,
  ObligationPostureResponse
} from '../../types';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Area, AreaChart
} from 'recharts';
import {
  ShieldCheck, AlertTriangle, FileText, Activity,
  ShieldAlert, RefreshCw, Loader2, Info, ChevronRight, BarChart3
} from 'lucide-react';
import { Badge } from '../common/Badge';

export function UnifiedAnalyticsDashboard() {
  const [viewState, setViewState] = useState<'LOADING' | 'READY' | 'ERROR'>('LOADING');
  const [error, setError] = useState<string | null>(null);

  const [orgPosture, setOrgPosture] = useState<OrganizationPostureResponse | null>(null);
  const [regPostures, setRegPostures] = useState<RegulationPostureResponse[]>([]);
  const [oblPostures, setOblPostures] = useState<ObligationPostureResponse[]>([]);
  const [history, setHistory] = useState<OrganizationPostureResponse[]>([]);

  const fetchDashboardData = async () => {
    setViewState('LOADING');
    setError(null);
    try {
      const [org, regs, obls, hist] = await Promise.all([
        ServiceAPI.getOrganizationPosture().catch(e => {
          if (e.response?.status === 404) return null;
          throw e;
        }),
        ServiceAPI.getRegulationPostures().catch(() => []),
        ServiceAPI.getObligationPostures().catch(() => []),
        ServiceAPI.getOrganizationPostureHistory().catch(() => [])
      ]);

      setOrgPosture(org);
      setRegPostures(regs || []);
      setOblPostures(obls || []);
      
      // Sort history chronologically
      const sortedHistory = (hist || []).sort(
        (a, b) => new Date(a.evaluated_at).getTime() - new Date(b.evaluated_at).getTime()
      );
      setHistory(sortedHistory);
      
      setViewState('READY');
    } catch (err: any) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        setError('Unauthorized to access compliance analytics.');
      } else {
        setError('Failed to load compliance dashboard data.');
      }
      setViewState('ERROR');
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  if (viewState === 'LOADING') {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  if (viewState === 'ERROR') {
    return (
      <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-6 rounded-2xl flex items-start gap-4 animate-in fade-in">
        <AlertTriangle className="w-6 h-6 flex-shrink-0" />
        <div>
          <h3 className="text-lg font-bold">Access Error</h3>
          <p className="mt-1">{error}</p>
        </div>
      </div>
    );
  }

  const isNoApplicableRequirements = orgPosture?.posture_status === 'NO_APPLICABLE_REQUIREMENTS';
  
  // Historical chart data
  const chartData = history.map(h => ({
    date: new Date(h.evaluated_at).toLocaleDateString(),
    time: new Date(h.evaluated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    compliance: h.posture_status === 'NO_APPLICABLE_REQUIREMENTS' ? 100 : (h.compliance_percentage || 0),
    gaps: h.total_control_gaps || 0,
    satisfied: h.total_satisfied_obligations || 0,
    status: h.posture_status
  }));

  const gapObligations = oblPostures.filter(o => o.posture_status === 'CONTROL_GAP');
  const reviewObligations = oblPostures.filter(o => o.review_required);

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-brand-400" />
            Unified Compliance Analytics
          </h1>
          <p className="text-slate-400 mt-1">
            Deterministic, read-only analytics dashboard powered by the Phase 5 Posture Engine.
          </p>
        </div>
        <button
          onClick={fetchDashboardData}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh Data
        </button>
      </div>

      {!orgPosture && (
        <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 text-center">
          <ShieldAlert className="w-12 h-12 text-slate-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-white">No Posture Data</h3>
          <p className="text-slate-400 mt-1">
            The posture engine has not evaluated this organization yet. Ensure regulations are mapped and controls are assessed.
          </p>
        </div>
      )}

      {orgPosture && (
        <>
          {/* SECTION A: Overall Compliance */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className={`col-span-1 md:col-span-2 p-6 rounded-2xl border ${isNoApplicableRequirements ? 'bg-slate-800/40 border-slate-700' : orgPosture.posture_status === 'SATISFIED' ? 'bg-green-950/20 border-green-900/50' : 'bg-brand-950/20 border-brand-900/30'} flex flex-col justify-center`}>
              <h2 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-2">Overall Compliance Posture</h2>
              <div className="flex items-end gap-4">
                {isNoApplicableRequirements ? (
                  <span className="text-4xl font-bold text-slate-300">No Applicable Requirements</span>
                ) : (
                  <>
                    <span className="text-5xl font-bold text-white">{orgPosture.compliance_percentage?.toFixed(1) ?? '0.0'}%</span>
                    <span className={`text-lg font-bold mb-1 ${orgPosture.posture_status === 'SATISFIED' ? 'text-green-400' : orgPosture.posture_status === 'CONTROL_GAP' ? 'text-red-400' : 'text-amber-400'}`}>
                      {orgPosture.posture_status.replace(/_/g, ' ')}
                    </span>
                  </>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-4 flex items-center gap-1">
                <Info className="w-3 h-3" /> Last evaluated: {new Date(orgPosture.evaluated_at).toLocaleString()} (Engine: {orgPosture.engine_version})
              </p>
            </div>
            
            <div className="glass-panel p-6 rounded-2xl border border-slate-800">
              <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-4">Obligations</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Applicable</span>
                  <span className="font-bold text-white">{orgPosture.total_applicable_obligations}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Satisfied</span>
                  <span className="font-bold text-green-400">{orgPosture.total_satisfied_obligations}</span>
                </div>
              </div>
            </div>
            
            <div className="glass-panel p-6 rounded-2xl border border-slate-800">
              <h3 className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-4">Action Required</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Control Gaps</span>
                  <span className="font-bold text-red-400">{orgPosture.total_control_gaps}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-300">Review Required</span>
                  <span className="font-bold text-amber-400">{orgPosture.total_review_required}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-8">
              {/* SECTION F: Historical Compliance Trend */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800">
                <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-brand-400" />
                  Historical Compliance Trend
                </h3>
                {chartData.length > 1 ? (
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorCompliance" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis 
                          dataKey="date" 
                          stroke="#64748b" 
                          fontSize={12} 
                          tickLine={false} 
                          axisLine={false} 
                          minTickGap={30}
                        />
                        <YAxis 
                          stroke="#64748b" 
                          fontSize={12} 
                          tickLine={false} 
                          axisLine={false}
                          domain={[0, 100]}
                          tickFormatter={(val) => `${val}%`}
                        />
                        <RechartsTooltip 
                          contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '0.5rem', color: '#f8fafc' }}
                          itemStyle={{ color: '#e2e8f0' }}
                          labelStyle={{ color: '#94a3b8', marginBottom: '0.25rem' }}
                          formatter={(value: any, name: string) => [
                            name === 'compliance' ? `${Number(value).toFixed(1)}%` : value, 
                            name.charAt(0).toUpperCase() + name.slice(1)
                          ]}
                          labelFormatter={(label, payload) => payload.length > 0 ? `${label} ${payload[0].payload?.time || ''}` : label}
                        />
                        <Area 
                          type="monotone" 
                          dataKey="compliance" 
                          stroke="#3b82f6" 
                          strokeWidth={2}
                          fillOpacity={1} 
                          fill="url(#colorCompliance)" 
                          activeDot={{ r: 6, fill: '#3b82f6', stroke: '#0f172a', strokeWidth: 2 }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-64 flex flex-col items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
                    <Activity className="w-8 h-8 mb-2 opacity-20" />
                    <p>Insufficient historical data for trend analysis.</p>
                    <p className="text-xs mt-1">More data points will appear as posture is re-evaluated.</p>
                  </div>
                )}
              </div>

              {/* SECTION B: Regulation Posture */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800 overflow-hidden">
                <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-brand-400" />
                  Regulation Posture Breakdown
                </h3>
                
                {regPostures.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
                          <th className="p-3 font-medium">Regulation</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium text-right">Applicable</th>
                          <th className="p-3 font-medium text-right">Satisfied</th>
                          <th className="p-3 font-medium text-right">Gaps</th>
                        </tr>
                      </thead>
                      <tbody className="text-sm">
                        {regPostures.map((reg) => {
                          const isNoApp = reg.posture_status === 'NO_APPLICABLE_REQUIREMENTS';
                          const pct = reg.applicable_obligation_count > 0 
                            ? (reg.satisfied_obligation_count / reg.applicable_obligation_count) * 100 
                            : 100;
                            
                          return (
                            <tr key={reg.regulation_id} className="border-b border-slate-800/50 hover:bg-slate-900/30 transition-colors">
                              <td className="p-3 align-middle">
                                <div className="font-medium text-slate-200">{reg.regulation_title || reg.regulation_id.substring(0,8)}</div>
                              </td>
                              <td className="p-3 align-middle">
                                {isNoApp ? (
                                  <Badge level="NONE">No Applicable Req</Badge>
                                ) : reg.posture_status === 'SATISFIED' ? (
                                  <Badge level="BRAND">Satisfied ({pct.toFixed(0)}%)</Badge>
                                ) : reg.posture_status === 'CONTROL_GAP' ? (
                                  <Badge level="HIGH">Control Gap ({pct.toFixed(0)}%)</Badge>
                                ) : (
                                  <Badge level="MEDIUM">{reg.posture_status.replace(/_/g, ' ')}</Badge>
                                )}
                              </td>
                              <td className="p-3 text-right text-slate-300 font-mono">{reg.applicable_obligation_count}</td>
                              <td className="p-3 text-right text-green-400 font-mono">{reg.satisfied_obligation_count}</td>
                              <td className="p-3 text-right font-mono">
                                {reg.control_gap_count > 0 ? (
                                  <span className="text-red-400 font-bold">{reg.control_gap_count}</span>
                                ) : (
                                  <span className="text-slate-500">0</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-6 text-slate-500">
                    No regulations are currently mapped to this organization.
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-8">
              {/* SECTION E: Review Required */}
              <div className="glass-panel p-6 rounded-2xl border border-amber-900/30 bg-amber-950/10">
                <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  Action Items: Reviews
                </h3>
                {reviewObligations.length > 0 ? (
                  <div className="space-y-3">
                    {reviewObligations.map(obl => (
                      <div key={obl.obligation_id} className="bg-slate-900/50 p-3 rounded-xl border border-slate-800">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <span className="text-[10px] font-bold tracking-wider uppercase text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded mb-1 inline-block">
                              Obligation Review
                            </span>
                            <p className="text-sm font-medium text-slate-200 line-clamp-2">
                              {obl.obligation_title || obl.obligation_id}
                            </p>
                            {obl.missing_information && Object.keys(obl.missing_information).length > 0 && (
                              <p className="text-xs text-amber-500/80 mt-1">
                                Missing info: {Object.keys(obl.missing_information).join(', ')}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-slate-500 text-sm">
                    No items currently require manual review.
                  </div>
                )}
              </div>

              {/* SECTION D: Obligation Gaps */}
              <div className="glass-panel p-6 rounded-2xl border border-red-900/30 bg-red-950/10">
                <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-red-400" />
                  Action Items: Gaps
                </h3>
                {gapObligations.length > 0 ? (
                  <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                    {gapObligations.map(obl => (
                      <div key={obl.obligation_id} className="bg-slate-900/50 p-3 rounded-xl border border-red-900/30">
                        <span className="text-[10px] font-bold tracking-wider uppercase text-red-400 bg-red-400/10 px-2 py-0.5 rounded mb-1 inline-block">
                          Control Gap
                        </span>
                        <p className="text-sm font-medium text-slate-200 mb-1 line-clamp-2">
                          {obl.obligation_title || obl.obligation_id}
                        </p>
                        {obl.mapped_control_id ? (
                          <div className="text-xs bg-slate-950 p-2 rounded border border-slate-800 text-slate-400">
                            <span className="block text-slate-500 mb-0.5">Mapped Control:</span>
                            {obl.mapped_control_title || obl.mapped_control_id}
                          </div>
                        ) : (
                          <div className="text-xs bg-slate-950 p-2 rounded border border-slate-800 text-slate-400 italic">
                            No control mapped to this obligation.
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-slate-500 text-sm">
                    No control gaps detected.
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
