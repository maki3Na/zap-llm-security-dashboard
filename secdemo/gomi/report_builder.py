# secdemo/report_builder.py
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime

def build_report_input(site: str, alerts: List[Dict[str, Any]], history_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")

    norm_alerts = []
    for a in alerts:
        norm_alerts.append({
            "risk": a.get("risk", ""),
            "name": a.get("name", ""),
            "url": a.get("url", ""),
            "param": a.get("param", ""),
            "evidence": a.get("evidence", ""),
            "cweid": a.get("cweid", ""),
            "wascid": a.get("wascid", ""),
            "desc": a.get("desc", ""),
            "solution": a.get("solution", ""),
            "reference": a.get("reference", ""),
        })

    norm_hist = []
    for h in history_items[:300]:
        norm_hist.append({
            "time": h.get("time", ""),
            "method": h.get("method", ""),
            "status": h.get("status", ""),
            "url": h.get("url", ""),
        })

    return {
        "generated_at": now,
        "target_site": site,
        "alerts": norm_alerts,
        "history": norm_hist,
        "counts": {"alerts": len(norm_alerts), "history": len(norm_hist)},
    }
