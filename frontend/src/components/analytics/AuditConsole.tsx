import React, { useState } from 'react';
import { Lock, Key, FileCheck, Search, Filter, ShieldAlert, UserCheck } from 'lucide-react';
import { AuditLog } from '../../types';
import { formatDateTime } from '../../utils/formatTime';

interface AuditConsoleProps {
  auditLogs: AuditLog[];
}

// ---------------------------------------------------------------------------
// AuditConsole — Audit & Defense pillar, Audit Trail tab
// Responsible for: immutable event log, audit search/filter, security posture
// Enterprise Profile / User Management moved to Settings > Enterprise Profile
// ---------------------------------------------------------------------------
export const AuditConsole: React.FC<AuditConsoleProps> = ({ auditLogs = [] }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');

  const filteredLogs = (auditLogs || []).filter((log) => {
    const matchesSearch =
      log.user_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.target_type.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesAction = actionFilter === 'ALL' || log.action.includes(actionFilter);
    return matchesSearch && matchesAction;
  });

  return (
    <div className="space-y-6">
      {/* Security Health Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-semibold uppercase">Data Encryption</span>
            <Lock className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-lg font-bold text-white">AES-256 & TLS 1.3</span>
          <p className="text-[10px] text-slate-400">Encrypted at rest & in transit</p>
        </div>
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-semibold uppercase">Access Control</span>
            <Key className="w-4 h-4 text-brand-400" />
          </div>
          <span className="text-lg font-bold text-white">Strict RBAC Active</span>
          <p className="text-[10px] text-slate-400">Least-privilege isolation</p>
        </div>
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-semibold uppercase">Audit Log Storage</span>
            <FileCheck className="w-4 h-4 text-indigo-400" />
          </div>
          <span className="text-lg font-bold text-white">Cryptographic Log</span>
          <p className="text-[10px] text-slate-400">Immutable event ledger</p>
        </div>
        <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-semibold uppercase">Security Threats</span>
            <ShieldAlert className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-lg font-bold text-emerald-400">0 Threat Alerts</span>
          <p className="text-[10px] text-slate-400">Real-time WAF active</p>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl glass-panel border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by user, action, or target type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-brand-500"
          >
            <option value="ALL">All Event Actions</option>
            <option value="TASK">Task Actions</option>
            <option value="WORKFLOW">Workflow Transitions</option>
            <option value="GRAPH">Knowledge Graph Mappings</option>
            <option value="INGEST">Ingestion Events</option>
          </select>
        </div>
      </div>

      {/* Immutable Audit Log Table */}
      <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden">
        <div className="p-4 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <UserCheck className="w-4 h-4 text-emerald-400" />
            Audit Event Ledger ({filteredLogs.length} records)
          </h2>
          <span className="text-[10px] text-slate-400 font-mono">Append-Only · Immutable</span>
        </div>
        <div className="divide-y divide-slate-800/80">
          {filteredLogs.map((log) => (
            <div key={log.id} className="p-4 hover:bg-slate-900/50 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-white">{log.user_name}</span>
                  <span className="px-2 py-0.5 text-[9px] font-bold bg-brand-500/20 text-brand-300 rounded font-mono border border-brand-500/30">
                    {log.user_role}
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="font-mono text-emerald-400 font-semibold">{log.action}</span>
                </div>
                {log.details && (
                  <p className="text-[11px] text-slate-400 font-mono bg-slate-950 p-2 rounded-lg border border-slate-800 inline-block">
                    {JSON.stringify(log.details)}
                  </p>
                )}
              </div>
              <div className="text-right space-y-0.5 flex-shrink-0">
                <span className="text-[10px] text-slate-400 block uppercase">{log.target_type}</span>
                <span className="text-[11px] text-slate-300 font-mono">{formatDateTime(log.created_at)}</span>
              </div>
            </div>
          ))}
          {filteredLogs.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-xs font-medium">
              {auditLogs.length === 0
                ? 'No audit log records yet. Actions taken in the platform will appear here.'
                : 'No audit records match the current search filter.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
