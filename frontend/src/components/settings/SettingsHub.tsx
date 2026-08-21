import React, { useState } from "react";
import { Settings, Radio, RefreshCw, Building2 } from "lucide-react";
import { RegulatorySource } from "../../types";
import { SourceManager } from "../sources/SourceManager";
import { BatchReExtractionDashboard } from "../admin/BatchReExtractionDashboard";
import { EnterpriseProfilePanel } from "./EnterpriseProfilePanel";

interface SettingsHubProps {
  sources: RegulatorySource[];
  onTriggerCrawl: (id: string) => Promise<any>;
  onAddSource: (data: any) => Promise<any>;
  onDeleteSource: (id: string) => Promise<any>;
  onDiscoverAgain?: () => void;
}

type SettingsTab = "profile" | "sources" | "batch";

// ---------------------------------------------------------------------------
// Settings Hub — IA v3.0
// Tabs: Enterprise Profile | Regulatory Sources & Feeds | Batch Re-Extraction
// Enterprise Profile moved here from AuditConsole where it did not belong.
// All components are reused as-is; this is a navigation wrapper only.
// ---------------------------------------------------------------------------
export const SettingsHub: React.FC<SettingsHubProps> = ({
  sources,
  onTriggerCrawl,
  onAddSource,
  onDeleteSource,
  onDiscoverAgain,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>("profile");

  const tabs: { id: SettingsTab; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: "profile", label: "Organization Profile", icon: Building2 },
    { id: "sources", label: "Regulatory Sources & Feeds", icon: Radio },
    { id: "batch", label: "Batch Re-Extraction", icon: RefreshCw },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Settings className="w-5 h-5 text-slate-400" />
          <h1 className="text-lg font-bold text-white tracking-tight">Settings</h1>
        </div>
        <p className="text-xs text-slate-400">
          Configure your enterprise profile, regulatory source feeds, and data extraction operations.
          Administrator access required for Sources and Batch tabs.
        </p>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-2 p-1 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-semibold w-fit flex-wrap">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
              activeTab === id
                ? "bg-slate-700 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
            aria-selected={activeTab === id}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "profile" && <EnterpriseProfilePanel onDiscoverAgain={onDiscoverAgain} />}

      {activeTab === "sources" && (
        <SourceManager
          sources={sources}
          onTriggerCrawl={onTriggerCrawl}
          onAddSource={onAddSource}
          onDeleteSource={onDeleteSource}
        />
      )}

      {activeTab === "batch" && <BatchReExtractionDashboard />}
    </div>
  );
};

