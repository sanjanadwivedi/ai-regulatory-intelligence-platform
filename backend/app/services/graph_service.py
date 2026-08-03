import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.domain import (
    Regulation, Section, Obligation, Requirement,
    KnowledgeGraphChain, ComplianceTask
)

logger = logging.getLogger("compliance_platform.graph")


def _slug(value: Optional[str]) -> str:
    """
    Create a stable, collision-resistant graph node ID from an entity code
    (e.g. 'CTRL-KYC-04' → 'ctrl-kyc-04').  We key on the real-world entity
    code, not on the DB row's UUID — so two chains sharing the same policy
    code collapse into one shared node, which is the correct graph behaviour.
    """
    if not value:
        return ""
    return re.sub(r"[^a-z0-9\-]", "-", value.lower()).strip("-")


def _safe_label(value: Optional[str], fallback: str = "Unknown") -> str:
    """Return a printable label; never emit the literal string 'None'."""
    if value and value != "None":
        return value
    return fallback


class KnowledgeGraphEngine:
    """
    Knowledge Graph Engine.
    Traverses and dynamically constructs relationship chains from real DB data:
    Regulation → Section → Requirement → Control → Policy → Process → Department → Application → Task.

    Node deduplication keys on entity codes (control_code, policy_code, …),
    not on DB row UUIDs, so shared controls/policies appear as single nodes
    with multiple incoming edges — the actual value of a knowledge graph.
    """

    @staticmethod
    def get_regulation_graph(regulation_id: str, db: Session = None) -> Dict[str, Any]:
        if not db or not regulation_id:
            logger.warning(
                "get_regulation_graph called without db or regulation_id — returning fallback graph"
            )
            return KnowledgeGraphEngine.get_fallback_graph(regulation_id or "unknown")

        reg = db.query(Regulation).filter(Regulation.id == regulation_id).first()
        if not reg:
            reg = db.query(Regulation).filter(
                (Regulation.doc_number == regulation_id) |
                (Regulation.id.like(f"%{regulation_id}%"))
            ).first()

        if not reg:
            logger.warning("Regulation '%s' not found — returning fallback graph", regulation_id)
            return KnowledgeGraphEngine.get_fallback_graph(regulation_id)

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids: set = set()

        def add_node(node_id: str, node: Dict[str, Any]) -> bool:
            """Add node only if its id is not already present. Returns True if added."""
            if node_id in node_ids:
                return False
            nodes.append(node)
            node_ids.add(node_id)
            return True

        def add_edge(source: str, target: str, label: str) -> None:
            """Add edge only if both endpoints exist in the graph."""
            if source in node_ids and target in node_ids:
                edges.append({"source": source, "target": target, "label": label})
            else:
                logger.debug(
                    "Skipped dangling edge %s→%s (missing node ids)", source, target
                )

        # ----------------------------------------------------------------
        # 1. Regulation root node
        # ----------------------------------------------------------------
        reg_node_id = f"reg-{_slug(reg.id[:12])}"
        add_node(reg_node_id, {
            "id": reg_node_id,
            "label": reg.title[:50] + ("…" if len(reg.title) > 50 else ""),
            "type": "REGULATION",
            "category": f"{reg.authority} Mandate",
            "color": "border-brand-500 bg-brand-950/60 text-brand-300",
        })

        # ----------------------------------------------------------------
        # 2. Sections → Obligations → Requirements (per-regulation, real DB)
        # ----------------------------------------------------------------
        # Build a lookup from requirement_id → req_node_id for chain linking
        req_node_map: Dict[str, str] = {}

        sections = db.query(Section).filter(Section.regulation_id == reg.id).all()
        for sec in sections:
            sec_node_id = f"sec-{_slug(sec.id[:12])}"
            if add_node(sec_node_id, {
                "id": sec_node_id,
                "label": f"{sec.section_number}: {_safe_label(sec.title, 'Clause')}",
                "type": "SECTION",
                "category": "Statutory Clause",
                "color": "border-blue-500 bg-blue-950/60 text-blue-300",
            }):
                add_edge(reg_node_id, sec_node_id, "contains")

            obs = db.query(Obligation).filter(Obligation.section_id == sec.id).all()
            for ob in obs:
                reqs = db.query(Requirement).filter(Requirement.obligation_id == ob.id).all()
                for req in reqs:
                    req_node_id = f"req-{_slug(req.id[:12])}"
                    req_node_map[req.id] = req_node_id
                    label = req.requirement_text[:45] + "…" if len(req.requirement_text) > 45 else req.requirement_text
                    if add_node(req_node_id, {
                        "id": req_node_id,
                        "label": label,
                        "type": "REQUIREMENT",
                        "category": "Statutory Obligation",
                        "color": "border-emerald-500 bg-emerald-950/60 text-emerald-300",
                    }):
                        add_edge(sec_node_id, req_node_id, "enforces")

        # ----------------------------------------------------------------
        # 3. KnowledgeGraphChains: Control → Policy → Process → Dept → App
        #    Node IDs are keyed on entity codes, NOT chain row UUIDs.
        #    This means two chains sharing the same policy collapse to one node.
        #    None codes are skipped (not rendered as "None: …").
        # ----------------------------------------------------------------
        chains = db.query(KnowledgeGraphChain).filter(
            KnowledgeGraphChain.regulation_id == reg.id
        ).all()

        for chain in chains:
            # Determine correct upstream anchor for this chain:
            # prefer the requirement linked by the chain; fall back to reg root.
            if chain.requirement_id and chain.requirement_id in req_node_map:
                upstream = req_node_map[chain.requirement_id]
            else:
                # Use first requirement node if any exist, else reg root
                req_nodes = [n["id"] for n in nodes if n["type"] == "REQUIREMENT"]
                upstream = req_nodes[0] if req_nodes else reg_node_id

            # CONTROL
            if chain.control_code:
                ctrl_id = f"ctrl-{_slug(chain.control_code)}"
                if add_node(ctrl_id, {
                    "id": ctrl_id,
                    "label": f"{chain.control_code}: Enterprise Control",
                    "type": "CONTROL",
                    "category": "Internal Control",
                    "color": "border-amber-500 bg-amber-950/60 text-amber-300",
                }):
                    add_edge(upstream, ctrl_id, "monitored by")
                ctrl_upstream = ctrl_id
            else:
                ctrl_upstream = upstream

            # POLICY
            if chain.policy_code:
                pol_id = f"pol-{_slug(chain.policy_code)}"
                if add_node(pol_id, {
                    "id": pol_id,
                    "label": f"{chain.policy_code}: Corporate Policy",
                    "type": "POLICY",
                    "category": "Enterprise Policy",
                    "color": "border-indigo-500 bg-indigo-950/60 text-indigo-300",
                }):
                    add_edge(ctrl_upstream, pol_id, "governed by")
                pol_upstream = pol_id
            else:
                pol_upstream = ctrl_upstream

            # PROCESS
            if chain.process_code:
                prc_id = f"prc-{_slug(chain.process_code)}"
                if add_node(prc_id, {
                    "id": prc_id,
                    "label": f"{chain.process_code}: Workflow",
                    "type": "PROCESS",
                    "category": "Business Process",
                    "color": "border-purple-500 bg-purple-950/60 text-purple-300",
                }):
                    add_edge(pol_upstream, prc_id, "executed via")
                prc_upstream = prc_id
            else:
                prc_upstream = pol_upstream

            # DEPARTMENT
            dept_name = chain.department_name
            if dept_name:
                dept_id = f"dept-{_slug(dept_name)}"
                if add_node(dept_id, {
                    "id": dept_id,
                    "label": dept_name,
                    "type": "DEPARTMENT",
                    "category": "Organizational Unit",
                    "color": "border-fuchsia-500 bg-fuchsia-950/60 text-fuchsia-300",
                }):
                    add_edge(prc_upstream, dept_id, "owned by")
                dept_upstream = dept_id
            else:
                dept_upstream = prc_upstream

            # APPLICATION
            if chain.application_code:
                app_id = f"app-{_slug(chain.application_code)}"
                if add_node(app_id, {
                    "id": app_id,
                    "label": f"{chain.application_code}: System",
                    "type": "APPLICATION",
                    "category": "IT Application",
                    "color": "border-cyan-500 bg-cyan-950/60 text-cyan-300",
                }):
                    add_edge(dept_upstream, app_id, "uses system")

        # ----------------------------------------------------------------
        # 4. Compliance Tasks — linked by control_code match, not position
        # ----------------------------------------------------------------
        # Build a lookup of control_code → app_id for task attachment
        ctrl_to_app: Dict[str, str] = {}
        for chain in chains:
            if chain.control_code and chain.application_code:
                ctrl_to_app[chain.control_code] = f"app-{_slug(chain.application_code)}"

        tasks = db.query(ComplianceTask).filter(
            ComplianceTask.regulation_id == reg.id
        ).all()
        for t in tasks:
            task_id = f"task-{_slug(t.id[:12])}"
            if add_node(task_id, {
                "id": task_id,
                "label": t.title[:45] + "…" if len(t.title) > 45 else t.title,
                "type": "TASK",
                "category": "Compliance Action",
                "color": "border-rose-500 bg-rose-950/60 text-rose-300",
            }):
                # Prefer the app node for this task's control_code
                if t.control_code and t.control_code in ctrl_to_app:
                    source = ctrl_to_app[t.control_code]
                else:
                    # Fall back to any app node, then reg root
                    app_nodes = [n["id"] for n in nodes if n["type"] == "APPLICATION"]
                    source = app_nodes[0] if app_nodes else reg_node_id
                add_edge(source, task_id, "triggers action")

        logger.info(
            "Built graph for '%s': %d nodes, %d edges", regulation_id, len(nodes), len(edges)
        )
        return {
            "regulation_id": reg.id,
            "title": reg.title,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "data_source": "live_db",
        }

    @staticmethod
    def get_fallback_graph(regulation_id: str) -> Dict[str, Any]:
        """
        Static fallback returned only when db is unavailable or the regulation
        is not found.  Clearly marked as fallback in the response.
        """
        nodes = [
            {"id": "reg-1", "label": "RBI KYC Master Direction 2026", "type": "REGULATION", "category": "Legal Mandate", "color": "border-brand-500 bg-brand-950/60 text-brand-300"},
            {"id": "sec-1", "label": "Section 4.1(a)", "type": "SECTION", "category": "Statutory Clause", "color": "border-blue-500 bg-blue-950/60 text-blue-300"},
            {"id": "req-1", "label": "Mandatory 2-Year High-Risk V-CIP", "type": "REQUIREMENT", "category": "Obligation", "color": "border-emerald-500 bg-emerald-950/60 text-emerald-300"},
            {"id": "ctrl-kyc-04", "label": "CTRL-KYC-04: High-Risk Cadence Check", "type": "CONTROL", "category": "Internal Control", "color": "border-amber-500 bg-amber-950/60 text-amber-300"},
            {"id": "pol-kyc-2026", "label": "POL-KYC-2026: Retail Onboarding Policy v3.2", "type": "POLICY", "category": "Enterprise Policy", "color": "border-indigo-500 bg-indigo-950/60 text-indigo-300"},
            {"id": "prc-onboarding-01", "label": "PRC-ONBOARDING-01: V-CIP Authentication", "type": "PROCESS", "category": "Business Process", "color": "border-purple-500 bg-purple-950/60 text-purple-300"},
            {"id": "dept-retail-banking", "label": "Retail Banking Operations", "type": "DEPARTMENT", "category": "Organizational Unit", "color": "border-fuchsia-500 bg-fuchsia-950/60 text-fuchsia-300"},
            {"id": "app-core-banking", "label": "APP-CORE-BANKING: Customer Master DB", "type": "APPLICATION", "category": "IT System", "color": "border-cyan-500 bg-cyan-950/60 text-cyan-300"},
            {"id": "task-1", "label": "Task-201: Update SOP-KYC-3.2", "type": "TASK", "category": "Compliance Task", "color": "border-rose-500 bg-rose-950/60 text-rose-300"},
        ]
        edges = [
            {"source": "reg-1", "target": "sec-1", "label": "contains"},
            {"source": "sec-1", "target": "req-1", "label": "enforces"},
            {"source": "req-1", "target": "ctrl-kyc-04", "label": "monitored by"},
            {"source": "ctrl-kyc-04", "target": "pol-kyc-2026", "label": "governed by"},
            {"source": "pol-kyc-2026", "target": "prc-onboarding-01", "label": "executed via"},
            {"source": "prc-onboarding-01", "target": "dept-retail-banking", "label": "owned by"},
            {"source": "dept-retail-banking", "target": "app-core-banking", "label": "uses system"},
            {"source": "app-core-banking", "target": "task-1", "label": "triggers action"},
        ]
        return {
            "regulation_id": regulation_id,
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "data_source": "fallback_static",
        }
