# secdemo/ui_tool_ai.py
from __future__ import annotations

import streamlit as st

from secdemo.ai_ollama import OllamaChatClient, DEFAULT_SYSTEM


def _ensure_report_blocks() -> None:
    st.session_state.setdefault("report_blocks", [])


def _push_report_block(title: str, content_md: str) -> None:
    _ensure_report_blocks()
    st.session_state["report_blocks"].append({"title": title, "md": content_md})


def summarize_tool_output(tool_name: str, output: str) -> str:
    client = OllamaChatClient(st.session_state["ollama_base"])
    model = st.session_state["ollama_model"]
    temp = float(st.session_state.get("ollama_temp", 0.2))

    prompt = f"""
以下は {tool_name} の実行結果です。
この結果から次を要約してください。

1) 検出された重要ポイント（箇条書き）
2) セキュリティ上の意味（影響/前提条件）
3) 次に取るべき調査・対応（防御側）

制約:
- 攻撃手順・PoC・悪用方法は書かない
- “可能性” と “前提条件” を明確に
- 守る側の判断材料を重視

--- 実行結果 ---
{output}
"""

    return client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        system=DEFAULT_SYSTEM,
    )


def render_tool_ai_summary() -> None:
    st.subheader("🤖 外部ツール結果のAI要約（レポート連携）")

    _ensure_report_blocks()

    # --- sqlmap ---
    sql_out = st.session_state.get("sqlmap_output", "")
    if sql_out:
        col1, col2 = st.columns([1, 1], gap="small")
        with col1:
            if st.button("🧠 sqlmap 結果をAI要約", use_container_width=True, key="ai_sqlmap"):
                with st.spinner("AIが要約中..."):
                    st.session_state["sqlmap_ai"] = summarize_tool_output("sqlmap", sql_out)
                    _push_report_block("sqlmap AI要約", st.session_state["sqlmap_ai"])
        with col2:
            st.caption("※ 要約は report_blocks に自動追加されます")

        if st.session_state.get("sqlmap_ai"):
            st.markdown("### sqlmap AI要約")
            st.markdown(st.session_state["sqlmap_ai"])
    else:
        st.caption("sqlmap 未実行")

    st.divider()

    # --- nmap ---
    nmap_out = st.session_state.get("nmap_output", "")
    if nmap_out:
        col1, col2 = st.columns([1, 1], gap="small")
        with col1:
            if st.button("🧠 nmap 結果をAI要約", use_container_width=True, key="ai_nmap"):
                with st.spinner("AIが要約中..."):
                    st.session_state["nmap_ai"] = summarize_tool_output("nmap", nmap_out)
                    _push_report_block("nmap AI要約", st.session_state["nmap_ai"])
        with col2:
            st.caption("※ 要約は report_blocks に自動追加されます")

        if st.session_state.get("nmap_ai"):
            st.markdown("### nmap AI要約")
            st.markdown(st.session_state["nmap_ai"])
    else:
        st.caption("nmap 未実行")
