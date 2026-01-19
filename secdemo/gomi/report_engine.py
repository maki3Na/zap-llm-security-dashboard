from __future__ import annotations
from typing import List, Dict, Any, Optional




RISK_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Informational": 4,
    "Info": 4,
}


def extract_alerts(zap_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    # ZAPのalerts形式（zap_client.fetch_alerts の返りを想定）
    if not zap_json:
        return []
    if isinstance(zap_json, dict) and "alerts" in zap_json:
        return zap_json.get("alerts") or []
    # それ以外（アップロード形式）にも最低限対応
    return zap_json.get("site", [{}])[0].get("alerts", []) if isinstance(zap_json, dict) else []


def sort_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(a):
        r = a.get("risk") or a.get("riskdesc") or ""
        r = r.split(" ")[0]
        return (RISK_ORDER.get(r, 99), (a.get("alert") or a.get("name") or ""))
    return sorted(alerts or [], key=key)


def filter_alerts(alerts: List[Dict[str, Any]], min_risk: str = "Medium", keyword: str = "", top_n: int = 0) -> List[Dict[str, Any]]:
    min_rank = RISK_ORDER.get(min_risk, 2)
    kw = (keyword or "").lower().strip()

    out = []
    for a in alerts or []:
        risk = (a.get("risk") or a.get("riskdesc") or "Informational").split(" ")[0]
        rank = RISK_ORDER.get(risk, 99)
        if rank > min_rank:
            continue
        name = (a.get("alert") or a.get("name") or "")
        url = (a.get("url") or "")
        param = (a.get("param") or "")
        blob = f"{risk} {name} {url} {param}".lower()
        if kw and kw not in blob:
            continue
        out.append({
            "risk": risk,
            "name": name,
            "url": url,
            "param": param,
            "evidence": a.get("evidence") or "",
            "desc": a.get("desc") or a.get("description") or "",
            "solution": a.get("solution") or "",
            "reference": a.get("reference") or "",
        })

    if top_n and top_n > 0:
        out = out[:top_n]
    return out


def build_zap_prompt(alerts_used: List[Dict[str, Any]], report_title: str, report_scope: str, extra_instructions: str) -> str:
    lines = []
    lines.append(f"# 診断報告書（ドラフト）")
    lines.append("")
    lines.append(f"## 案件名")
    lines.append(report_title)
    lines.append("")
    lines.append(f"## 対象範囲")
    lines.append(report_scope)
    lines.append("")
    lines.append("## 重要な指示")
    lines.append(extra_instructions)
    lines.append("")
    lines.append("## ZAPアラート一覧（入力）")
    for i, a in enumerate(alerts_used, 1):
        lines.append(f"- [{i:02d}] Risk={a['risk']} / {a['name']}")
        lines.append(f"  - URL: {a['url']}")
        if a.get("param"):
            lines.append(f"  - Param: {a['param']}")
        if a.get("evidence"):
            lines.append(f"  - Evidence: {a['evidence']}")
    lines.append("")
    lines.append("## 出力要件")
    lines.append("- 日本語・ですます調")
    lines.append("- 重要度順に並べる")
    lines.append("- 各項目に「根拠」「影響」「再現/確認観点」「推奨対策」を入れる")
    lines.append("- 誤検知の可能性があるなら、その理由と追加確認を必ず書く")
    return "\n".join(lines)


def build_combined_prompt(
    alerts_used: List[Dict[str, Any]],
    report_title: str,
    report_scope: str,
    extra_instructions: str,
    intruder_results: Optional[List[Dict[str, Any]]] = None,
    quick_ai_summary: Optional[Dict[str, Any]] = None,
    quick_ai_raw: str = "",
) -> str:
    base = build_zap_prompt(alerts_used, report_title, report_scope, extra_instructions)

    lines = [base]
    lines.append("")
    lines.append("---")
    lines.append("## 追加入力（手動検査/補助ツール）")

    # Intruder
    intruder_results = intruder_results or []
    if intruder_results:
        lines.append("")
        lines.append("### Intruder結果（差分のあるもの中心）")
        for r in intruder_results[:200]:
            diffs = []
            if r.get("d_status"):
                diffs.append("status差分")
            if r.get("d_length"):
                diffs.append(f"length差分(Δ{r.get('delta_length')})")
            rx_diff = [k for k, v in (r.get("regex_diff") or {}).items() if v]
            if rx_diff:
                diffs.append("regex差分: " + ", ".join(rx_diff[:6]))

            if not diffs:
                continue

            lines.append(f"- no={r.get('no')} param={r.get('param')} payload={repr(r.get('payload'))}")
            lines.append(f"  - status={r.get('status')} length={r.get('length')}")
            lines.append(f"  - diff={'; '.join(diffs)}")

    else:
        lines.append("")
        lines.append("### Intruder結果")
        lines.append("(なし)")

    # QuickCheck (AI summary)
    if quick_ai_summary:
        lines.append("")
        lines.append("### QuickCheck結果（AI要約JSON）")
        lines.append("```json")
        import json as _json
        lines.append(_json.dumps(quick_ai_summary, ensure_ascii=False, indent=2))
        lines.append("```")
    elif quick_ai_raw:
        lines.append("")
        lines.append("### QuickCheck結果（生出力）")
        lines.append("```")
        lines.append(quick_ai_raw[:12000])
        lines.append("```")
    else:
        lines.append("")
        lines.append("### QuickCheck結果")
        lines.append("(なし)")

    lines.append("")
    lines.append("## 統合出力要件（追加）")
    lines.append("- ZAPアラートに加えて、Intruder/QuickCheckで得た“差分”や“根拠”も引用して報告に反映する")
    lines.append("- ただし、確証が弱いものは「要追加確認」と明示する")
    lines.append("- 報告書末尾に「実行した検査（コマンド/手順）」の章を作る")

    return "\n".join(lines)
