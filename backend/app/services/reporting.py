"""Report generation - JSON and HTML exports combined from scan results."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

from app.services.risk import overall_risk, SEVERITY_RANK

CATEGORY_LABELS = {
    "system_prompt_extraction": "System Prompt Extraction",
    "developer_instruction_extraction": "Developer Instruction Extraction",
    "instruction_override": "Instruction Override",
    "policy_bypass": "Policy Bypass",
    "role_manipulation": "Role Manipulation",
    "constraint_bypass": "Constraint Bypass",
    "instruction_hierarchy_confusion": "Instruction Hierarchy Confusion",
    "confidential_information": "Confidential Information",
    "obfuscation": "Obfuscation",
    "context_attack": "Context Manipulation",
    "multi_turn": "Multi-Turn",
    "multilingual": "Multilingual",
    "rag_indirect": "RAG / Indirect Injection",
    "agent_tool": "Agent / Tool",
}

CLASSIFICATION_LABELS = {
    "blocked": "Blocked",
    "partial": "Partial",
    "success": "Success",
    "uncertain": "Uncertain",
    "error": "Error",
}


def build_finding_dict(finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "title": finding.title,
        "category": finding.category,
        "category_label": CATEGORY_LABELS.get(finding.category, finding.category),
        "severity": finding.severity,
        "confidence": finding.confidence,
        "attack_id": finding.attack_id,
        "attack_objective": finding.attack_objective,
        "payload": finding.payload,
        "target_response": finding.target_response,
        "evidence": finding.evidence,
        "violated_boundary": finding.violated_boundary,
        "root_cause": finding.root_cause,
        "remediation": finding.remediation,
        "reproduction": finding.reproduction or {},
    }


def build_report_data(scan, target, results, findings) -> dict[str, Any]:
    counts = {
        "total": len(results),
        "success": 0,
        "partial": 0,
        "blocked": 0,
        "uncertain": 0,
        "error": 0,
    }
    for r in results:
        cls = r.classification
        if cls in counts:
            counts[cls] += 1
        else:
            counts["uncertain"] += 1

    confs = [r.confidence for r in results]
    avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0

    breakdown_map: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r.attack.category if r.attack else "unknown"
        entry = breakdown_map.setdefault(
            cat,
            {
                "category": cat,
                "category_label": CATEGORY_LABELS.get(cat, cat),
                "attempted": 0,
                "success": 0,
                "partial": 0,
                "blocked": 0,
            },
        )
        entry["attempted"] += 1
        if r.classification in entry:
            entry[r.classification] += 1

    severity_counts = {"info": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    for r in results:
        if r.severity in severity_counts:
            severity_counts[r.severity] += 1

    top_findings = sorted(findings, key=lambda f: (SEVERITY_RANK.get(f.severity, 0), f.confidence), reverse=True)

    return {
        "scan": {
            "id": scan.id,
            "name": scan.name or f"Scan #{scan.id}",
            "status": scan.status,
            "started_at": _iso(scan.started_at),
            "ended_at": _iso(scan.ended_at),
            "generated_at": _iso(datetime.now(timezone.utc)),
        },
        "target": {
            "id": target.id,
            "name": target.name,
            "url": target.url,
            "adapter_type": target.adapter_type,
        },
        "summary": {
            **counts,
            "overall_risk": overall_risk(counts),
            "avg_confidence": avg_conf,
        },
        "breakdown": sorted(breakdown_map.values(), key=lambda e: -e["attempted"]),
        "severity_counts": severity_counts,
        "top_vulnerabilities": [
            CATEGORY_LABELS.get(f.category, f.category)
            for f in top_findings[:8]
        ] or ["None confirmed"],
        "findings": [build_finding_dict(f) for f in findings],
    }


def build_summary_dict(counts: dict[str, int]) -> dict[str, Any]:
    return {
        **counts,
        "overall_risk": overall_risk(counts),
    }


def to_json(report_data: dict[str, Any]) -> str:
    return json.dumps(report_data, indent=2, ensure_ascii=False)


def to_html(report_data: dict[str, Any]) -> str:
    s = report_data["summary"]
    rows = "".join(
        "<tr>"
        f"<td>{_e(f['category_label'])}</td>"
        f"<td>{f['attempted']}</td>"
        f"<td>{f.get('success', 0)}</td>"
        f"<td>{f.get('partial', 0)}</td>"
        f"<td>{f.get('blocked', 0)}</td>"
        "</tr>"
        for f in report_data["breakdown"]
    )
    findings_html = ""
    for f in report_data["findings"]:
        findings_html += f"""
        <div class="finding sev-{_e(f['severity'])}">
          <h3>[{_e(f['severity'].upper())}] {_e(f['title'])} <span class="conf">conf {f['confidence']:.0%}</span></h3>
          <p><b>Attack:</b> {_e(f['attack_id'] or '-')} — {_e(f['attack_objective'] or '')}</p>
          <pre class="payload">{_e(f['payload'] or '')}</pre>
          <p><b>Target response:</b></p>
          <pre>{_e((f['target_response'] or '')[:2000])}</pre>
          <p><b>Evidence:</b> {_e(f['evidence'] or '')}</p>
          <p><b>Violated boundary:</b> {_e(f['violated_boundary'] or '')}</p>
          <p><b>Root cause:</b> {_e(f['root_cause'] or 'n/a')}</p>
          <p><b>Remediation:</b> {_e(f['remediation'] or '')}</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Security Report — {_e(report_data['scan']['name'])}</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 2rem auto; max-width: 960px; color: #1f2937; line-height: 1.55; }}
h1 {{ border-bottom: 2px solid #111; padding-bottom: .4rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #d1d5db; padding: .5rem .75rem; text-align: left; }}
th {{ background: #f3f4f6; }}
.badge {{ display:inline-block; padding:.15rem .6rem; border-radius:999px; font-weight:600; font-size:.85rem; }}
.risk-critical,.risk-high {{ background:#fee2e2; color:#b91c1c; }}
.risk-medium {{ background:#ffedd5; color:#c2410c; }}
.risk-low {{ background:#d1fae5; color:#065f46; }}
.finding {{ border:1px solid #e5e7eb; border-radius:8px; padding:1rem 1.2rem; margin:1rem 0; }}
.finding h3 {{ margin:0 0 .5rem; }}
.sev-critical {{ border-left:6px solid #b91c1c; }}
.sev-high {{ border-left:6px solid #ea580c; }}
.sev-medium {{ border-left:6px solid #d97706; }}
.sev-low {{ border-left:6px solid #65a30d; }}
.sev-info {{ border-left:6px solid #6b7280; }}
pre {{ background:#f9fafb; padding:.75rem; border-radius:6px; overflow-x:auto; white-space:pre-wrap; }}
.conf {{ font-weight:600; color:#6b7280; }}
</style></head><body>
<h1>{_e(report_data['scan']['name'])} — Security Report</h1>
<p>Target: {_e(report_data['target']['name'])} ({_e(report_data['target']['url'])})<br>
Generated: {_e(report_data['scan']['generated_at'])} · Scan ID: {report_data['scan']['id']}</p>
<h2>Executive Summary</h2>
<p>Tests run: <b>{s['total']}</b> ·
<span class="badge risk-{_e(s['overall_risk'])}">{_e(s['overall_risk'].upper())} risk</span></p>
<ul>
<li>Successful attacks: <b>{s['success']}</b></li>
<li>Partial: <b>{s['partial']}</b>, Blocked: <b>{s['blocked']}</b></li>
<li>Uncertain: <b>{s['uncertain']}</b>, Errors: <b>{s['error']}</b></li>
<li>Avg confidence: <b>{s['avg_confidence']:.0%}</b></li>
</ul>
<h2>Attack Breakdown</h2>
<table><tr><th>Category</th><th>Attempted</th><th>Success</th><th>Partial</th><th>Blocked</th></tr>{rows}</table>
<h2>Findings ({len(report_data['findings'])})</h2>
{findings_html or '<p>No confirmed vulnerabilities.</p>'}
</body></html>"""


def _iso(dt) -> str:
    return dt.isoformat() if dt else None


def _e(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""