import React, { useState } from 'react';
import { GitBranch, Layers, ShieldCheck, ArrowRight, Filter, Info, ChevronRight } from 'lucide-react';

export interface GraphNode {
  id: string;
  label: string;
  type: 'REGULATION' | 'SECTION' | 'REQUIREMENT' | 'CONTROL' | 'POLICY' | 'PROCESS' | 'DEPARTMENT' | 'APPLICATION' | 'TASK';
  category: string;
  color: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

interface KnowledgeGraphCanvasProps {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  regulationId?: string;
  onNodeClick?: (node: GraphNode) => void;
}

const DEFAULT_NODES: GraphNode[] = [
  { id: 'reg-1', label: 'RBI KYC Master Direction 2026', type: 'REGULATION', category: 'Legal Mandate', color: 'border-brand-500 bg-brand-950/60 text-brand-300' },
  { id: 'sec-1', label: 'Section 4.1(a)', type: 'SECTION', category: 'Statutory Clause', color: 'border-blue-500 bg-blue-950/60 text-blue-300' },
  { id: 'req-1', label: 'Mandatory 2-Yr High-Risk V-CIP', type: 'REQUIREMENT', category: 'Obligation', color: 'border-emerald-500 bg-emerald-950/60 text-emerald-300' },
  { id: 'ctrl-1', label: 'CTRL-KYC-04: Cadence Check', type: 'CONTROL', category: 'Internal Control', color: 'border-amber-500 bg-amber-950/60 text-amber-300' },
  { id: 'pol-1', label: 'POL-KYC-2026: SOP-KYC-3.2', type: 'POLICY', category: 'Enterprise Policy', color: 'border-indigo-500 bg-indigo-950/60 text-indigo-300' },
  { id: 'prc-1', label: 'PRC-ONBOARDING-01: V-CIP Auth', type: 'PROCESS', category: 'Business Process', color: 'border-purple-500 bg-purple-950/60 text-purple-300' },
  { id: 'dept-1', label: 'Retail Banking Operations', type: 'DEPARTMENT', category: 'Organizational Unit', color: 'border-fuchsia-500 bg-fuchsia-950/60 text-fuchsia-300' },
  { id: 'app-1', label: 'APP-CORE-BANKING: Customer DB', type: 'APPLICATION', category: 'IT System', color: 'border-cyan-500 bg-cyan-950/60 text-cyan-300' },
  { id: 'task-1', label: 'Task-201: Revise SOP Cadence', type: 'TASK', category: 'Compliance Task', color: 'border-rose-500 bg-rose-950/60 text-rose-300' }
];

const DEFAULT_EDGES: GraphEdge[] = [
  { source: 'reg-1', target: 'sec-1', label: 'contains' },
  { source: 'sec-1', target: 'req-1', label: 'enforces' },
  { source: 'req-1', target: 'ctrl-1', label: 'monitored by' },
  { source: 'ctrl-1', target: 'pol-1', label: 'governed by' },
  { source: 'pol-1', target: 'prc-1', label: 'executed via' },
  { source: 'prc-1', target: 'dept-1', label: 'owned by' },
  { source: 'dept-1', target: 'app-1', label: 'uses system' },
  { source: 'app-1', target: 'task-1', label: 'triggers task' }
];

import { ServiceAPI } from '../../services/api';

export const KnowledgeGraphCanvas: React.FC<KnowledgeGraphCanvasProps> = ({
  nodes: initialNodes,
  edges: initialEdges,
  regulationId,
  onNodeClick,
}) => {
  const [graphNodes, setGraphNodes] = React.useState<GraphNode[]>(initialNodes || DEFAULT_NODES);
  const [graphEdges, setGraphEdges] = React.useState<GraphEdge[]>(initialEdges || DEFAULT_EDGES);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState<boolean>(false);

  React.useEffect(() => {
    const fetchGraph = async () => {
      setLoading(true);
      try {
        const data = await ServiceAPI.getKnowledgeGraph(regulationId);
        if (data && data.nodes && data.nodes.length > 0) {
          setGraphNodes(data.nodes);
          setGraphEdges(data.edges || []);
          setSelectedNode(data.nodes[0]);
        } else if (initialNodes) {
          setGraphNodes(initialNodes);
          setGraphEdges(initialEdges || []);
          setSelectedNode(initialNodes[0]);
        }
      } catch {
        // Keep current nodes
      } finally {
        setLoading(false);
      }
    };
    fetchGraph();
  }, [regulationId]);

  const nodes = graphNodes;
  const edges = graphEdges;

  const filteredNodes = activeFilter === 'ALL' ? nodes : nodes.filter(n => n.type === activeFilter);

  return (
    <div className="space-y-4">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl glass-panel border border-slate-800">
        <div className="flex items-center space-x-2">
          <GitBranch className="w-5 h-5 text-brand-400" />
          <div>
            <h2 className="text-sm font-bold text-white">Enterprise Knowledge Graph Canvas</h2>
            <p className="text-xs text-slate-400">
              Interactive 8-hop relationship chain linking regulation text to controls, SOP policies, and tasks.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
          >
            <option value="ALL">All Graph Nodes ({nodes.length})</option>
            <option value="REGULATION">Regulations</option>
            <option value="REQUIREMENT">Requirements</option>
            <option value="CONTROL">Controls</option>
            <option value="POLICY">Policies</option>
            <option value="TASK">Tasks</option>
          </select>
        </div>
      </div>

      {/* Visual Canvas Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Node Pipeline Flow Visualizer */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 space-y-4 relative overflow-x-auto">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Knowledge Graph Relationship Flow
            </span>
            <span className="text-[10px] bg-brand-500/20 text-brand-300 px-2 py-0.5 rounded font-mono border border-brand-500/30">
              8-Hop Traversal Active
            </span>
          </div>

          <div className="flex flex-col space-y-3 py-2">
            {filteredNodes.map((node, i) => {
              const edge = edges.find(e => e.source === node.id);
              const isSelected = selectedNode?.id === node.id;

              return (
                <div key={node.id} className="flex flex-col items-center">
                  <div
                    onClick={() => {
                      setSelectedNode(node);
                      if (onNodeClick) onNodeClick(node);
                    }}
                    className={`w-full p-4 rounded-xl border-2 transition-all cursor-pointer shadow-lg flex items-center justify-between ${node.color} ${
                      isSelected ? 'ring-2 ring-brand-400 scale-[1.01]' : 'hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center space-x-3">
                      <span className="w-6 h-6 rounded-full bg-slate-900/80 font-mono text-[10px] font-bold flex items-center justify-center text-slate-300 border border-slate-700">
                        0{i + 1}
                      </span>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] uppercase font-extrabold tracking-wider opacity-80">{node.category}</span>
                          <span className="text-slate-500">•</span>
                          <span className="text-[10px] font-mono opacity-80">{node.type}</span>
                        </div>
                        <h4 className="text-xs font-bold text-white mt-0.5">{node.label}</h4>
                      </div>
                    </div>

                    <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? 'rotate-90 text-brand-300' : 'text-slate-500'}`} />
                  </div>

                  {edge && i < filteredNodes.length - 1 && (
                    <div className="flex flex-col items-center py-1.5">
                      <div className="w-0.5 h-3 bg-brand-500/50" />
                      <span className="text-[9px] font-mono uppercase bg-slate-900 px-2 py-0.5 rounded text-brand-300 border border-slate-800 my-0.5">
                        {edge.label}
                      </span>
                      <div className="w-0.5 h-3 bg-brand-500/50" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Node Details Drawer */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 pb-3 border-b border-slate-800">
            <Info className="w-4 h-4 text-brand-400" />
            <h3 className="text-sm font-bold text-white">Node Context & Metadata</h3>
          </div>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                <span className="text-[10px] font-bold text-brand-400 uppercase tracking-wider">{selectedNode.category}</span>
                <h4 className="text-sm font-bold text-white">{selectedNode.label}</h4>
                <p className="text-[10px] text-slate-400 font-mono">Node ID: {selectedNode.id}</p>
              </div>

              <div className="space-y-2">
                <span className="text-slate-400 font-semibold block">Node Properties</span>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-900 space-y-2 font-mono text-[11px]">
                  <div className="flex justify-between text-slate-300">
                    <span className="text-slate-500">Bound Domain:</span>
                    <span className="text-brand-300">Regulatory Knowledge</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span className="text-slate-500">Risk Exposure:</span>
                    <span className="text-rose-400 font-bold">HIGH (Score: 88)</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span className="text-slate-500">Audit Verifiable:</span>
                    <span className="text-emerald-400 font-bold">Yes (SOC2 Logged)</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-800">
                <span className="text-slate-400 font-semibold block">Connected Relations</span>
                <div className="space-y-1.5">
                  {edges
                    .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                    .map((e, idx) => (
                      <div key={idx} className="p-2 rounded-lg bg-slate-900 text-[10px] text-slate-300 flex items-center justify-between border border-slate-800">
                        <span>{e.source === selectedNode.id ? `➔ ${e.label} ➔ ${e.target}` : `⬅ ${e.label} ⬅ ${e.source}`}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-500 text-xs font-medium">
              Click any graph node to inspect context metadata.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
