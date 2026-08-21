import React, { useState } from "react";
import { ClipboardCheck, ShieldCheck, FileCheck } from "lucide-react";
import { ComplianceTask, TaskStatus } from "../../types";
import { TaskKanbanBoard } from "../tasks/TaskKanbanBoard";
import { ReviewsConsole } from "../reviews/ReviewsConsole";

interface ComplianceActionsHubProps {
  tasks: ComplianceTask[];
  onUpdateStatus: (taskId: string, status: TaskStatus) => void;
  onCreateTaskClick: () => void;
}

type ActionsTab = "tasks" | "signoffs";

// ---------------------------------------------------------------------------
// Compliance Actions Hub — IA v3.0 / Terminology Refinement
// Tabs: Tasks (TaskKanbanBoard) + Approvals (ReviewsConsole)
// ---------------------------------------------------------------------------
export const ComplianceActionsHub: React.FC<ComplianceActionsHubProps> = ({
  tasks,
  onUpdateStatus,
  onCreateTaskClick,
}) => {
  const [activeTab, setActiveTab] = useState<ActionsTab>("tasks");

  const pendingSignoffs = tasks.filter(
    (t) => t && (t.status === "WAITING_APPROVAL" || t.status === "NEEDS_REVIEW")
  ).length;

  const tabs: { id: ActionsTab; label: string; icon: React.FC<{ className?: string }>; badge?: number }[] = [
    { id: "tasks", label: "Tasks", icon: ClipboardCheck },
    { id: "signoffs", label: "Approvals", icon: ShieldCheck, badge: pendingSignoffs },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileCheck className="w-5 h-5 text-brand-400" />
            <h1 className="text-lg font-bold text-white tracking-tight">Compliance Actions</h1>
          </div>
          <p className="text-xs text-slate-400">
            Manage compliance tasks, track evidence, and process dual sign-off approvals.
          </p>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-2 p-1 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-semibold w-fit">
        {tabs.map(({ id, label, icon: Icon, badge }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
              activeTab === id
                ? "bg-brand-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
            aria-selected={activeTab === id}
          >
            <Icon className="w-4 h-4" />
            <span>{label}</span>
            {badge !== undefined && badge > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] font-bold bg-amber-500/20 text-amber-300 rounded-full border border-amber-500/30 animate-pulse">
                {badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "tasks" && (
        <TaskKanbanBoard
          tasks={tasks}
          onUpdateStatus={onUpdateStatus}
          onCreateTaskClick={onCreateTaskClick}
        />
      )}

      {activeTab === "signoffs" && (
        <ReviewsConsole tasks={tasks} onUpdateStatus={onUpdateStatus} />
      )}
    </div>
  );
};
