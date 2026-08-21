import React, { useState } from "react";
import { ShieldCheck, BarChart3, FileCheck2 } from "lucide-react";
import { AuditLog, AnalyticsOverview } from "../../types";
import { AuditConsole } from "../analytics/AuditConsole";
import { AnalyticsConsole } from "../analytics/AnalyticsConsole";

interface AuditDefenseHubProps {
  auditLogs: AuditLog[];
  analytics: AnalyticsOverview | null;
}

type AuditTab = "trail" | "analytics";

// ---------------------------------------------------------------------------
// Audit & Defense Hub — IA v3.0
// Merges: Security & Audit (AuditConsole) + Compliance Analytics (AnalyticsConsole)
// Both components are reused as-is; this is a navigation wrapper only.
// Primary value: traceability, evidence, and defense bundle export.
// ---------------------------------------------------------------------------
export const AuditDefenseHub: React.FC<AuditDefenseHubProps> = ({
  auditLogs,
  analytics,
}) => {
  const [activeTab, setActiveTab] = useState<AuditTab>("trail");

  const tabs: { id: AuditTab; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: "trail", label: "Audit Trail & Defense", icon: ShieldCheck },
    { id: "analytics", label: "Compliance Analytics", icon: BarChart3 },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <FileCheck2 className="w-5 h-5 text-emerald-400" />
          <h1 className="text-lg font-bold text-white tracking-tight">Audit & Defense</h1>
        </div>
        <p className="text-xs text-slate-400">
          Immutable compliance trail, regulatory decision history, and exportable examiner defense bundles.
        </p>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-2 p-1 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-semibold w-fit">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
              activeTab === id
                ? id === "trail"
                  ? "bg-emerald-700 text-white shadow"
                  : "bg-indigo-700 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
            aria-selected={activeTab === id}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content — reuses existing components unchanged */}
      {activeTab === "trail" && <AuditConsole auditLogs={auditLogs} />}
      {activeTab === "analytics" && (
        <AnalyticsConsole analytics={analytics} auditLogs={auditLogs} />
      )}
    </div>
  );
};
