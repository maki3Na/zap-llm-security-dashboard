# secdemo/ui_ai.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from secdemo.ai_ollama import OllamaChatClient, DEFAULT_SYSTEM


def _build_alert_explain_prompt(alert: Dict[str, Any]) -> str:
    return f"""以下は ZAP のアラート1件です。内容を「意味」「想定影響」「優先度判断」「推奨対策」「確認手順（安全な範囲）」で、短く分かりやすく説明してください。
許可のない対象への攻撃手順や悪用の具体化は書かないでください。

[Alert]
Risk: {alert.get('risk','')}
Name: {alert.get('name','')}
URL: {alert.get('url','')}
Param: {alert.get('param','')}
Evidence: {alert.get('evidence','')}
CWE: {alert.get('cweid','')}
WASC: {alert.get('wascid','')}
Description: {alert.get('desc','')}
Solution: {alert.get('solution','')}
Reference: {alert.get('reference','')}
"""


def generate_alert_explain(
    alert: Dict[str, Any],
    ollama_base: str,
    model: str,
    temperature: float = 0.2,
    timeout: int = 180,
) -> str:
    client = OllamaChatClient(base_url=ollama_base, timeout=timeout)

    # ✅ モデル存在チェック → なければ先頭モデルにフォールバック
    try:
        models = client.list_models()
    except Exception:
        models = []

    use_model = model
    if models and model not in models:
        use_model = models[0]  # とりあえず最初のモデルにする
        st.session_state["ollama_model"] = use_model  # UI側にも反映

    prompt = _build_alert_explain_prompt(alert)
    system = (
        DEFAULT_SYSTEM
        + "\nあなたはセキュリティ診断の説明担当です。具体的な悪用方法や攻撃手順は書かず、対策と判断に集中してください。"
    )
    return client.chat(
        model=use_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=float(temperature),
        system=system,
    )



def render_help_ai_dialog(
    zap_ok: bool,
    selected_site: str,
    hist_len: int,
    alert_len: int,
    url_filter: str,
) -> None:
    if not st.session_state.get("open_help_ai"):
        return

    st.session_state["open_help_ai"] = False

    @st.dialog("💬 ヘルプAI（質問対応）")
    def _dlg():
        st.write("このツールの使い方、ZAPの見方、検出事項の意味などを質問できます。")
        st.write("⚠️ 許可のない対象への攻撃手順や悪用の具体化には回答しません。")

        if "help_chat" not in st.session_state:
            st.session_state["help_chat"] = []

        base = st.session_state.get("ollama_base", "http://127.0.0.1:11434")
        client = OllamaChatClient(base_url=base, timeout=180)

        default_model = st.session_state.get("help_model", st.session_state.get("ollama_model", "qwen2.5-1.5b-instruct-q4_k_m"))
        try:
            models = client.list_models()
        except Exception:
            models = []

        if models:
            model = st.selectbox("Model", models, index=models.index(default_model) if default_model in models else 0)
        else:
            model = st.text_input("Model（手入力）", value=default_model)

        st.session_state["help_model"] = model
        temp = st.slider("Temperature", 0.0, 1.0, float(st.session_state.get("help_temp", 0.2)), 0.05)
        st.session_state["help_temp"] = temp

        context = {
            "zap_connected": zap_ok,
            "selected_site": selected_site,
            "history_items": hist_len,
            "alert_items": alert_len,
            "url_filter": url_filter,
        }

        for m in st.session_state["help_chat"]:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        prompt = st.chat_input("質問を入力（例：このアラートの意味は？/ 優先度の決め方は？）")
        if prompt:
            st.session_state["help_chat"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            system = DEFAULT_SYSTEM + "\n現在の状態:\n" + str(context)

            with st.chat_message("assistant"):
                with st.spinner("考え中..."):
                    answer = client.chat(
                        model=model,
                        messages=st.session_state["help_chat"],
                        temperature=float(temp),
                        system=system,
                    )
                st.markdown(answer)

            st.session_state["help_chat"].append({"role": "assistant", "content": answer})

        c1, c2 = st.columns(2)
        with c1:
            if st.button("履歴クリア", use_container_width=True):
                st.session_state["help_chat"] = []
                st.rerun()
        with c2:
            st.caption("※機密情報（トークン等）は貼らないでください。")

    _dlg()
