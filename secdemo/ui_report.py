# secdemo/ui_report.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from secdemo.ai_ollama import OllamaChatClient, DEFAULT_SYSTEM


def _ensure_report_blocks() -> None:
    st.session_state.setdefault("report_blocks", [])


def _risk_bucket(r: str) -> str:
    s = (r or "").lower()
    if "high" in s:
        return "High"
    if "medium" in s:
        return "Medium"
    if "low" in s:
        return "Low"
    return "Info"


def _alerts_overview(alert_items: List[Dict[str, Any]]) -> str:
    if not alert_items:
        return "（アラートなし）"

    counts = {"High": 0, "Medium": 0, "Low": 0, "Info": 0}
    for a in alert_items:
        counts[_risk_bucket(a.get("risk", ""))] += 1

    lines = [
        f"- High: {counts['High']}",
        f"- Medium: {counts['Medium']}",
        f"- Low: {counts['Low']}",
        f"- Info: {counts['Info']}",
        "",
        "### 検出一覧（上位）",
    ]

    # “見出し用”に上位だけ
    for a in alert_items[:30]:
        lines.append(f"- [{a.get('risk','')}] {a.get('name','')}  ({a.get('url','')})")
    if len(alert_items) > 30:
        lines.append(f"- ...（他 {len(alert_items)-30} 件）")

    return "\n".join(lines)


def _traffic_overview(hist_items: List[Dict[str, Any]]) -> str:
    if not hist_items:
        return "（履歴なし）"
    lines = ["### 通信ログ（抜粋）"]
    for h in hist_items[:25]:
        lines.append(f"- {h.get('method','')} {h.get('url','')}  ({h.get('status','')})")
    if len(hist_items) > 25:
        lines.append(f"- ...（他 {len(hist_items)-25} 件）")
    return "\n".join(lines)


def generate_overall_risk_report(hist_items, alert_items) -> str:
    """
    総合リスク評価（AI）
    - ZAP + 通信 + 外部ツールAI要約（あれば）を統合
    - 攻撃手順は禁止
    """
    client = OllamaChatClient(st.session_state["ollama_base"])
    model = st.session_state["ollama_model"]
    temp = float(st.session_state.get("ollama_temp", 0.2))

    sql_ai = st.session_state.get("sqlmap_ai", "未実施")
    nmap_ai = st.session_state.get("nmap_ai", "未実施")

    prompt = f"""
以下はWebセキュリティ診断の統合情報です。
“守る側”の観点で、全体リスクを評価してください。

【ZAPアラート概要】
{_alerts_overview(alert_items)}

【通信ログの特徴（抜粋）】
{_traffic_overview(hist_items)}

【sqlmap AI要約】
{sql_ai}

【nmap AI要約】
{nmap_ai}

出力要件:
- 重要リスクTop3（理由つき）
- 想定影響（業務影響/情報漏えい/改ざん/可用性）
- 優先対応（短期/中期）
- 追加調査の提案（防御側）

制約:
- 攻撃手順・PoC・悪用方法は書かない
- 断定しすぎず、前提条件・可能性を明記
"""
    return client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        system=DEFAULT_SYSTEM,
    )


def render_report_ui(hist_items, alert_items) -> None:
    st.subheader("📝 AI診断レポート生成（ZAP + 外部ツール連携）")
    _ensure_report_blocks()

    include_tool_ai = st.checkbox("外部ツールAI要約を含める", value=True, key="rep_inc_tool_ai")
    include_overall = st.checkbox("総合リスク評価（AI）を含める", value=True, key="rep_inc_overall")
    include_selected_alert_ai = st.checkbox("選択アラートAI要約（詳細で生成したもの）を含める", value=True, key="rep_inc_sel_ai")

    col1, col2 = st.columns([1, 1], gap="small")
    with col1:
        if st.button("📄 AIでレポート生成", use_container_width=True, key="gen_report"):
            with st.spinner("AIがレポートを生成しています..."):
                # ここで report_blocks も組み込む
                blocks = st.session_state.get("report_blocks", []) or []
                blocks_md = ""
                if include_tool_ai and blocks:
                    parts = []
                    for b in blocks[-10:]:  # 重くならないように直近だけ
                        parts.append(f"## {b.get('title','')}\n\n{b.get('md','')}")
                    blocks_md = "\n\n".join(parts)

                sel_ai = ""
                if include_selected_alert_ai and st.session_state.get("alert_ai_text"):
                    sel_ai = "## 選択アラートAI要約\n\n" + st.session_state["alert_ai_text"]

                overall_md = ""
                if include_overall:
                    overall_text = generate_overall_risk_report(hist_items, alert_items)
                    overall_md = "## 総合リスク評価（AI）\n\n" + overall_text
                    st.session_state["overall_risk_ai"] = overall_text

                prompt = f"""
以下はWebセキュリティ診断結果です。
IPA「安全なウェブサイトの作り方」を参考に、Markdown形式の診断報告書としてまとめてください。

条件:
- 攻撃手順・PoC・悪用方法は書かない
- 守る側（ブルーチーム）視点
- 非技術者にも伝わる表現を入れる（ただし薄くしすぎない）

【診断概要】
対象: {st.session_state.get('selected_site','(all)')}
日時: {datetime.now().strftime("%Y-%m-%d %H:%M")}

【アラート概要】
{_alerts_overview(alert_items)}

【通信ログ（抜粋）】
{_traffic_overview(hist_items)}

【追加情報（AI要約/外部ツール）】
{sel_ai}

{blocks_md}

{overall_md}

出力構成:
1. 概要
2. 検出された脆弱性（優先度つき）
3. 通信ログから見える特徴
4. 総合評価と対応優先度
5. 推奨対応方針（短期/中期）
"""
                client = OllamaChatClient(st.session_state["ollama_base"])
                model = st.session_state["ollama_model"]
                temp = float(st.session_state.get("ollama_temp", 0.2))

                md = client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temp,
                    system=DEFAULT_SYSTEM,
                )
                st.session_state["ai_report_md"] = md

    with col2:
        if st.button("🧹 レポート素材（AI要約）をクリア", use_container_width=True, key="clear_blocks"):
            st.session_state["report_blocks"] = []
            st.session_state.pop("ai_report_md", None)
            st.success("クリアしました。")

    if st.session_state.get("ai_report_md"):
        st.markdown("### 📄 生成されたレポート（Markdown）")
        st.markdown(st.session_state["ai_report_md"])

        st.download_button(
            "⬇ Markdownでダウンロード",
            data=st.session_state["ai_report_md"].encode("utf-8"),
            file_name="security_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
