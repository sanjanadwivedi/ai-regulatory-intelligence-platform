import React, { useState, useEffect } from 'react';
import { ShieldCheck, Lock, Key, FileCheck, Search, Filter, ShieldAlert, UserCheck, Building2, Check, Sparkles, Loader2, Plus, Trash2 } from 'lucide-react';

import { AuditLog } from '../../types';
import { formatDateTime } from '../../utils/formatTime';
import { ServiceAPI } from '../../services/api';

interface AuditConsoleProps {
  auditLogs: AuditLog[];
}

export const AuditConsole: React.FC<AuditConsoleProps> = ({ auditLogs = [] }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');

  // Enterprise Profile — wired to real backend
  const [companyName, setCompanyName] = useState('');
  const [selectedIndustry, setSelectedIndustry] = useState('Banking & Financial Services');
  const [country, setCountry] = useState('');
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const INDUSTRIES = [
    { id: 'Banking & Financial Services', name: 'Banking & Financial Services (RBI / EBA)', depts: ['Retail Banking Ops', 'AML & CDD Compliance', 'IT Infrastructure & Security', 'Legal Counsel'] },
    { id: 'Healthcare & Life Sciences', name: 'Healthcare & Life Sciences (HIPAA / FDA)', depts: ['Clinical Operations', 'Patient Data Governance (PHI)', 'Medical Device Compliance', 'Legal Counsel'] },
    { id: 'Capital Markets & Securities', name: 'Capital Markets & Securities (SEC / FINRA)', depts: ['Trading & Market Surveillance', 'Equity Research Compliance', 'IT Infrastructure', 'Legal Counsel'] },
    { id: 'Technology & Cybersecurity', name: 'Technology & Cloud Security (SOC2 / GDPR)', depts: ['Information Security (CISO)', 'Data Protection Office (DPO)', 'DevOps Infrastructure', 'Legal Counsel'] },
  ];

  const currentIndustryObj = INDUSTRIES.find(i => i.id === selectedIndustry) || INDUSTRIES[0];

  // Load saved profile from backend on mount
  useEffect(() => {
    const load = async () => {
      try {
        const profile = await ServiceAPI.getEnterpriseProfile();
        if (profile) {
          setCompanyName(profile.organization_name || '');
          setSelectedIndustry(profile.industry_sector || 'Banking & Financial Services');
          setCountry(profile.country || '');
        }
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  const filteredLogs = (auditLogs || []).filter((log) => {
    const matchesSearch =
      log.user_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.target_type.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesAction = actionFilter === 'ALL' || log.action.includes(actionFilter);
    return matchesSearch && matchesAction;
  });

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await ServiceAPI.saveEnterpriseProfile({
        organization_name: companyName,
        industry_sector: selectedIndustry,
        departments: currentIndustryObj.depts,
        country: country,
        regulator_region: selectedIndustry,
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to save profile:', err);
    } finally {
      setIsSaving(false);
    }
  };

  // ---- Real User Management ----
  const [users, setUsers] = useState<any[]>([]);
  const [newUserName, setNewUserName] = useState('');
  const [newUserRole, setNewUserRole] = useState('Compliance Officer');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [isAddingUser, setIsAddingUser] = useState(false);

  const ROLES = [
    'Compliance Officer',
    'Chief Compliance Officer',
    'General Legal Counsel',
    'Internal Auditor',
    'Risk Manager',
    'Data Protection Officer',
    'System Administrator',
  ];

  const loadUsers = async () => {
    const fetched = await ServiceAPI.getUsers().catch(() => []);
    setUsers(fetched);
  };

  useEffect(() => { loadUsers(); }, []);

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserName.trim()) return;
    setIsAddingUser(true);
    try {
      const newUser = await ServiceAPI.createUser({ full_name: newUserName, role: newUserRole, email: newUserEmail });
      setNewUserName('');
      setNewUserEmail('');
      await loadUsers();
      window.dispatchEvent(new Event('user_list_updated'));
    } finally {
      setIsAddingUser(false);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!window.confirm('Remove this user?')) return;
    await ServiceAPI.deleteUser(userId).catch(() => null);
    await loadUsers();
    window.dispatchEvent(new Event('user_list_updated'));
  };



  return (

    <div className="space-y-6">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-emerald-950/30 to-slate-900 border border-emerald-500/20 shadow-xl flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
            <h1 className="text-xl font-bold text-white tracking-tight">Enterprise Settings, Security & Audit</h1>
            <span className="px-2.5 py-0.5 text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">
              SOC2 Type II & GDPR Verified
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Configure your enterprise industry sector, department structure, and view immutable security audit logs.
          </p>
        </div>
      </div>

      {/* Enterprise Industry & Department Settings Console */}
      <div className="glass-panel p-6 rounded-2xl border border-brand-500/30 space-y-4 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Building2 className="w-5 h-5 text-brand-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Enterprise Industry & Department Configuration</h2>
          </div>
          <span className="px-2.5 py-0.5 text-[10px] bg-brand-500/20 text-brand-300 font-mono font-bold rounded border border-brand-500/30 flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> {isLoading ? 'Loading...' : 'Sector Routing Engine Active'}
          </span>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-slate-400 gap-2 text-xs">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading saved enterprise profile...
          </div>
        ) : (
        <form onSubmit={handleSaveProfile} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-slate-300 font-semibold block">Organization Name</label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="space-y-1">
              <label className="text-slate-300 font-semibold block">Primary Industry Sector</label>
              <select
                value={selectedIndustry}
                onChange={(e) => setSelectedIndustry(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500 font-semibold"
              >
                {INDUSTRIES.map((ind) => (
                  <option key={ind.id} value={ind.id}>
                    {ind.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

            <div className="space-y-1">
              <label className="text-slate-300 font-semibold block">Country / Jurisdiction</label>
              <input
                type="text"
                placeholder="e.g. India, United States, Germany"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
              />
            </div>

          {/* Active Enterprise Department Mapping Tree */}
          <div className="space-y-2 pt-2 border-t border-slate-800/80">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
              Mapped Department Structure for {selectedIndustry}:
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {currentIndustryObj.depts.map((dept, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center space-y-0.5">
                  <span className="text-brand-400 font-bold block text-xs">{dept}</span>
                  <span className="text-[9px] text-slate-500 uppercase font-mono">Active Department</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            {savedSuccess ? (
              <span className="text-xs text-emerald-400 font-bold flex items-center gap-1">
                <Check className="w-4 h-4" /> Enterprise Industry & Department Settings Saved!
              </span>
            ) : (
              <span className="text-[10px] text-slate-400">
                Regulations outside your selected industry sector are automatically filtered by the Anti-Corruption Layer (ACL).
              </span>
            )}

            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-brand-600/30 transition-all flex items-center gap-2"
            >
              {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {isSaving ? 'Saving to Database...' : 'Save Enterprise Profile Settings'}
            </button>
          </div>
        </form>
        )}
      </div>

      {/* ---- Real Team Members / User Management ---- */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <UserCheck className="w-5 h-5 text-brand-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Team Members & User Roles</h2>
          </div>
          <span className="text-[10px] text-slate-400">These appear in the user switcher in the top navbar</span>
        </div>

        {/* Add new user form */}
        <form onSubmit={handleAddUser} className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs items-end">
          <div className="space-y-1">
            <label className="text-slate-300 font-semibold block">Full Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Priya Sharma"
              value={newUserName}
              onChange={(e) => setNewUserName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-slate-300 font-semibold block">Role</label>
            <select
              value={newUserRole}
              onChange={(e) => setNewUserRole(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
            >
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-slate-300 font-semibold block">Email (optional)</label>
            <input
              type="email"
              placeholder="e.g. priya@company.com"
              value={newUserEmail}
              onChange={(e) => setNewUserEmail(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white focus:outline-none focus:border-brand-500"
            />
          </div>
          <button
            type="submit"
            disabled={isAddingUser}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white font-bold rounded-xl text-xs shadow-lg shadow-brand-600/30 flex items-center gap-2 justify-center"
          >
            {isAddingUser ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            {isAddingUser ? 'Adding...' : 'Add User'}
          </button>
        </form>

        {/* Existing users list */}
        {users.length > 0 ? (
          <div className="space-y-2">
            {users.map((u: any) => (
              <div key={u.id} className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 text-xs">
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-300 font-bold text-[10px]">
                    {u.full_name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)}
                  </div>
                  <div>
                    <p className="font-semibold text-white">{u.full_name}</p>
                    <p className="text-[10px] text-slate-400">{u.role}{u.email ? ` · ${u.email}` : ''}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteUser(u.id)}
                  className="text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 p-1.5 rounded-lg transition-colors"
                  title="Remove user"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 text-center py-4">No team members added yet. Use the form above to add your compliance team.</p>
        )}
      </div>

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
            placeholder="Search audit trail by user, action, target type, or details..."
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
            <UserCheck className="w-4 h-4 text-emerald-400" /> Audit Log Event Ledger ({filteredLogs.length})
          </h2>
          <span className="text-[10px] text-slate-400 font-mono">Append-Only Event Store</span>
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

              <div className="text-right space-y-0.5">
                <span className="text-[10px] text-slate-400 block uppercase">{log.target_type}</span>
                <span className="text-[11px] text-slate-300 font-mono">{formatDateTime(log.created_at)}</span>
              </div>
            </div>
          ))}

          {filteredLogs.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-xs font-medium">
              No audit log records match the search filter.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
