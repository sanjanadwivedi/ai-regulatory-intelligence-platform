import React, { useState, useEffect, useCallback } from "react";
import {
  Building2,
  Check,
  Loader2,
  UserCheck,
  Plus,
  Trash2,
  Sparkles,
  ExternalLink,
  Shield,
  Activity,
  Briefcase,
  Globe,
  Users,
  CheckCircle2,
  Edit3,
} from "lucide-react";
import { INDUSTRIES } from "../common/EnterpriseSetupModal";
import { ServiceAPI } from "../../services/api";

// ---------------------------------------------------------------------------
// Category Map for Confirmed Facts Presentation
// ---------------------------------------------------------------------------
const CATEGORY_MAP: Record<string, { label: string; icon: React.ReactNode }> = {
  COMPANY: { label: "Company Identity", icon: <Building2 className="w-4 h-4 text-blue-400" /> },
  BUSINESS_ACTIVITY: { label: "Business Activities", icon: <Activity className="w-4 h-4 text-purple-400" /> },
  PRODUCT_SERVICE: { label: "Products & Services", icon: <Briefcase className="w-4 h-4 text-emerald-400" /> },
  LOCATION: { label: "Locations & Regions", icon: <Globe className="w-4 h-4 text-amber-400" /> },
  DEPARTMENT: { label: "Functions & Departments", icon: <Users className="w-4 h-4 text-rose-400" /> },
  LICENSE: { label: "Regulatory Licenses & Authorizations", icon: <Shield className="w-4 h-4 text-brand-400" /> },
  REGULATORY_SIGNAL: { label: "Discovered Regulatory Signals", icon: <Shield className="w-4 h-4 text-cyan-400" /> },
};

export const EnterpriseProfilePanel: React.FC<{ onDiscoverAgain?: () => void }> = ({ onDiscoverAgain }) => {
  // ---- Profile & Facts State ----
  const [profile, setProfile] = useState<any>(null);
  const [confirmedFacts, setConfirmedFacts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Manual Edit State (Secondary / Controlled)
  const [isEditingManual, setIsEditingManual] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [selectedIndustry, setSelectedIndustry] = useState(INDUSTRIES[1].id);
  const [country, setCountry] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // ---- User Management State ----
  const ROLES = [
    "Compliance Officer",
    "Chief Compliance Officer",
    "General Legal Counsel",
    "Internal Auditor",
    "Risk Manager",
    "Data Protection Officer",
    "System Administrator",
  ];

  const [users, setUsers] = useState<any[]>([]);
  const [newUserName, setNewUserName] = useState("");
  const [newUserRole, setNewUserRole] = useState("Compliance Officer");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [isAddingUser, setIsAddingUser] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [profRes, factsRes, usersRes] = await Promise.allSettled([
        ServiceAPI.getEnterpriseProfile(),
        ServiceAPI.getDiscoveryFacts("CONFIRMED"),
        ServiceAPI.getUsers(),
      ]);

      if (profRes.status === "fulfilled" && profRes.value) {
        setProfile(profRes.value);
        setOrgName(profRes.value.organization_name || "");
        setSelectedIndustry(profRes.value.industry_sector || INDUSTRIES[1].id);
        setCountry(profRes.value.country || "");
      }

      if (factsRes.status === "fulfilled" && factsRes.value) {
        setConfirmedFacts(factsRes.value);
      }

      if (usersRes.status === "fulfilled" && usersRes.value) {
        setUsers(usersRes.value);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Save Manual Edit
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const currentInd = INDUSTRIES.find((i) => i.id === selectedIndustry) || INDUSTRIES[0];
      const updated = await ServiceAPI.saveEnterpriseProfile({
        organization_name: orgName,
        industry_sector: selectedIndustry,
        departments: profile?.departments && profile.departments.length > 0 ? profile.departments : currentInd.depts,
        country,
        regulator_region: selectedIndustry,
        discovery_status: "CONFIRMED",
      });
      setProfile(updated);
      setSavedSuccess(true);
      setIsEditingManual(false);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to update profile:", err);
    } finally {
      setIsSaving(false);
    }
  };

  // User Actions
  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserName.trim()) return;
    setIsAddingUser(true);
    try {
      await ServiceAPI.createUser({
        full_name: newUserName,
        role: newUserRole,
        email: newUserEmail,
      });
      setNewUserName("");
      setNewUserEmail("");
      const updatedUsers = await ServiceAPI.getUsers().catch(() => []);
      setUsers(updatedUsers);
      window.dispatchEvent(new Event("user_list_updated"));
    } finally {
      setIsAddingUser(false);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!window.confirm("Remove this user?")) return;
    await ServiceAPI.deleteUser(userId).catch(() => null);
    const updatedUsers = await ServiceAPI.getUsers().catch(() => []);
    setUsers(updatedUsers);
    window.dispatchEvent(new Event("user_list_updated"));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-400 gap-2 text-xs">
        <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
        Loading organization context...
      </div>
    );
  }

  // Group confirmed facts by category
  const groupedConfirmed = confirmedFacts.reduce((acc, fact) => {
    const cat = CATEGORY_MAP[fact.fact_type]?.label || "Other Confirmed Context";
    if (!acc[cat]) acc[cat] = { icon: CATEGORY_MAP[fact.fact_type]?.icon, items: [] };
    acc[cat].items.push(fact);
    return acc;
  }, {} as Record<string, { icon: React.ReactNode; items: any[] }>);

  return (
    <div className="space-y-8 max-w-5xl">
      {/* ---- Read-First Authoritative Organization Profile ---- */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl border border-slate-800 space-y-6 shadow-xl relative overflow-hidden">
        {/* Header Summary */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  {profile?.organization_name || "Enterprise Organization"}
                </h2>
                <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                  <span>{profile?.industry_sector || "Banking & Financial Services"}</span>
                  {profile?.country && (
                    <>
                      <span>·</span>
                      <span>{profile?.country}</span>
                    </>
                  )}
                  {profile?.website_url && (
                    <>
                      <span>·</span>
                      <a
                        href={profile.website_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-brand-400 hover:text-brand-300 flex items-center gap-1"
                      >
                        {profile.website_url.replace(/^https?:\/\//, "")}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <span className="px-3 py-1 text-xs bg-emerald-500/10 text-emerald-300 font-semibold rounded-full border border-emerald-500/20 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Confirmed Profile
            </span>

            {onDiscoverAgain && (
              <button
                type="button"
                onClick={onDiscoverAgain}
                className="btn-primary text-xs py-2 px-3.5 flex items-center gap-2 shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Discover Again</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setIsEditingManual(!isEditingManual)}
              className="btn-secondary text-xs py-2 px-3 flex items-center gap-1.5"
            >
              <Edit3 className="w-3.5 h-3.5" />
              <span>{isEditingManual ? "Close Editor" : "Edit"}</span>
            </button>
          </div>
        </div>

        {savedSuccess && (
          <div className="p-3 bg-emerald-950/40 border border-emerald-500/30 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-400" />
            Organization profile updated successfully.
          </div>
        )}

        {/* Secondary Manual Edit Form (Collapsible) */}
        {isEditingManual && (
          <form onSubmit={handleSaveProfile} className="p-5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-4 text-xs">
            <h3 className="font-bold text-white uppercase tracking-wider text-[11px] flex items-center gap-2">
              <Edit3 className="w-3.5 h-3.5 text-brand-400" /> Edit Organization Details
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-slate-300 font-semibold block">Organization Name</label>
                <input
                  type="text"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-semibold block">Country / Jurisdiction</label>
                <input
                  type="text"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  placeholder="e.g. India, United States"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-brand-500"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-slate-300 font-semibold block">Primary Industry Sector</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {INDUSTRIES.map((ind) => (
                  <div
                    key={ind.id}
                    onClick={() => setSelectedIndustry(ind.id)}
                    className={`p-3 rounded-lg cursor-pointer border transition-all text-xs ${
                      selectedIndustry === ind.id
                        ? "bg-brand-600/20 border-brand-500 text-white"
                        : "bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-semibold text-white">{ind.name}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">{ind.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setIsEditingManual(false)}
                className="btn-secondary text-xs py-1.5 px-3"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="btn-primary text-xs py-1.5 px-4 flex items-center gap-2"
              >
                {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save Changes
              </button>
            </div>
          </form>
        )}

        {/* ---- Confirmed Organization Context Grid (Composed View) ---- */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Discovered Organization Context (Evidence-Backed)
            </h3>
            <span className="text-[11px] text-slate-500">
              {confirmedFacts.length} findings verified with traceable evidence
            </span>
          </div>

          {confirmedFacts.length > 0 ? (
            <div className="space-y-6">
              {Object.entries(groupedConfirmed).map(([category, data]: [string, any]) => {
                const { icon, items } = data;
                const isSignalCategory = category === "Discovered Regulatory Signals";
                return (
                  <div key={category} className="space-y-3">
                    <div className="pb-2 border-b border-slate-800/60 space-y-1">
                      <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                        {icon}
                        {category}
                      </h4>
                      {isSignalCategory && (
                        <p className="text-[11px] text-cyan-300/70">
                          Potential regulatory relevance discovered from public evidence. Statutory applicability and obligation matching will be determined by the Regulatory Applicability Engine.
                        </p>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {items.map((fact: any) => (
                        <div
                          key={fact.id}
                          className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-4 space-y-2.5 hover:border-slate-700 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="font-semibold text-white text-xs">
                              {fact.fact_value}
                            </div>
                            {fact.fact_type === "REGULATORY_SIGNAL" ? (
                              <span className="text-[10px] text-cyan-300 font-medium bg-cyan-950/60 px-2 py-0.5 rounded-full border border-cyan-500/30 shrink-0">
                                Signal Verified
                              </span>
                            ) : (
                              <span className="text-[10px] text-emerald-400 font-medium bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 shrink-0">
                                Confirmed
                              </span>
                            )}
                          </div>

                          {fact.snippet && (
                            <div className="p-2.5 bg-slate-950/60 rounded-lg border border-slate-800/60 text-[11px] text-slate-300 italic leading-relaxed">
                              "{fact.snippet}"
                            </div>
                          )}

                          <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                            <span>
                              Confidence: {Math.round((fact.confidence || 0.85) * 100)}%
                            </span>
                            {fact.source_url && (
                              <a
                                href={fact.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-brand-400 hover:text-brand-300 flex items-center gap-1"
                              >
                                Source <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80 text-xs text-slate-400 text-center py-6 space-y-2">
              <p>No automated discovery facts confirmed yet.</p>
              {onDiscoverAgain && (
                <button
                  type="button"
                  onClick={onDiscoverAgain}
                  className="text-xs text-brand-400 hover:text-brand-300 font-semibold underline"
                >
                  Start Discovery to extract verified organizational facts
                </button>
              )}
            </div>
          )}

          {/* Manually Configured Departments & Functions */}
          {profile?.departments && profile.departments.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-slate-800/60">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <Users className="w-4 h-4 text-slate-400" />
                Configured Departments & Functions
              </h4>
              <div className="flex flex-wrap gap-2">
                {profile.departments.map((d: string, i: number) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-[11px] font-medium"
                  >
                    {d}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ---- User & Role Management ---- */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <UserCheck className="w-5 h-5 text-brand-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Team Members & User Roles
            </h2>
          </div>
          <span className="text-[10px] text-slate-400">
            These appear in the user switcher in the top navbar
          </span>
        </div>

        <form
          onSubmit={handleAddUser}
          className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs items-end"
        >
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
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-slate-300 font-semibold block">
              Email (optional)
            </label>
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
            {isAddingUser ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Plus className="w-3.5 h-3.5" />
            )}
            {isAddingUser ? "Adding..." : "Add User"}
          </button>
        </form>

        {users.length > 0 ? (
          <div className="space-y-2">
            {users.map((u: any) => (
              <div
                key={u.id}
                className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 text-xs"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-300 font-bold text-[10px]">
                    {u.full_name
                      .split(" ")
                      .map((n: string) => n[0])
                      .join("")
                      .toUpperCase()
                      .slice(0, 2)}
                  </div>
                  <div>
                    <p className="font-semibold text-white">{u.full_name}</p>
                    <p className="text-[10px] text-slate-400">
                      {u.role}
                      {u.email ? ` · ${u.email}` : ""}
                    </p>
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
          <p className="text-xs text-slate-500 text-center py-4">
            No team members added yet. Use the form above to add your compliance team.
          </p>
        )}
      </div>
    </div>
  );
};
