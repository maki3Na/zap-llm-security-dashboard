# secdemo/ui.py
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from secdemo.zap_live_client import ZapLiveClient
from secdemo.url_reconstruct import reconstruct_url

from secdemo.ui_tables import render_history_table, render_alerts_table
from secdemo.ui_details import render_bookmarks_panel, render_history_details
from secdemo.ui_ai import render_help_ai_dialog, generate_alert_explain
from secdemo.ai_ollama import OllamaChatClient

from secdemo.ui_report import render_report_ui, generate_overall_risk_report
from secdemo.ui_tools import render_tool_ui
from secdemo.ui_tool_ai import render_tool_ai_summary


# =========================================================
# Settings persistence
# =========================================================
def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _settings_path() -> str:
    root = _project_root()
    data_dir = os.path.join(root, "secdemo_data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "ui_settings.json")


def _load_settings() -> Dict[str, Any]:
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_settings(d: Dict[str, Any]) -> None:
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _format_zap_time(v: Any) -> str:
    if not v:
        return ""
    s = str(v)
    if s.isdigit():
        try:
            n = int(s)
            if n > 10_000_000_000:
                return datetime.fromtimestamp(n / 1000).strftime("%Y-%m-%d %H:%M:%S")
            return datetime.fromtimestamp(n).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return s


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


# =========================================================
# Main App
# =========================================================
def render_app() -> None:
    # -----------------------------
    # Initial load
    # -----------------------------
    if "settings_loaded" not in st.session_state:
        saved = _load_settings()
        st.session_state.update(
            {
                "remember_settings": saved.get("remember_settings", True),
                "zap_base": saved.get("zap_base", "http://127.0.0.1:8080"),
                "apikey": saved.get("apikey", ""),
                "ollama_base": saved.get("ollama_base", "http://127.0.0.1:11434"),
                "ollama_model": saved.get("ollama_model", ""),
                "ollama_temp": float(saved.get("ollama_temp", 0.2)),
                "keyword": saved.get("keyword", ""),
                "history_count": int(saved.get("history_count", 200)),
                "bookmarks": saved.get("bookmarks", []) or [],
                "selected_alert": None,
                "selected_history_id": None,
                "settings_loaded": True,
            }
        )

    # -----------------------------
    # Sidebar
    # -----------------------------
    with st.sidebar:
        st.markdown("## 🔌 ZAP接続")

        st.session_state["remember_settings"] = st.checkbox(
            "設定を保存（ローカル）",
            value=st.session_state.get("remember_settings", True),
        )

        st.session_state["zap_base"] = st.text_input(
            "ZAP Base URL", value=st.session_state["zap_base"]
        )
        st.session_state["apikey"] = st.text_input(
            "ZAP API Key", value=st.session_state["apikey"], type="password"
        )

        st.markdown("## 🔄 更新")
        refresh_sec = st.selectbox("Auto refresh (sec)", [0, 2, 5, 10], index=2)
        st.session_state["history_count"] = st.slider(
            "History rows", 50, 500, st.session_state["history_count"], step=50
        )

        st.markdown("## 🔎 フィルタ")
        st.session_state["keyword"] = st.text_input(
            "URL contains", value=st.session_state["keyword"]
        )

        st.markdown("## 🤖 AI設定")
        st.session_state["ollama_base"] = st.text_input(
            "Ollama Base URL", value=st.session_state["ollama_base"]
        )

        # モデル一覧
        models: List[str] = []
        try:
            client = OllamaChatClient(st.session_state["ollama_base"], timeout=10)
            models = client.list_models()
        except Exception:
            pass

        saved_model = st.session_state.get("ollama_model", "")
        if models:
            if saved_model not in models:
                saved_model = models[0]
            st.session_state["ollama_model"] = st.selectbox(
                "Model", models, index=models.index(saved_model)
            )
        else:
            st.session_state["ollama_model"] = st.text_input(
                "Model（手入力）", value=saved_model or "gemma2:9b-instruct-q5_K_M"
            )

        st.session_state["ollama_temp"] = st.slider(
            "Temperature", 0.0, 1.0, st.session_state["ollama_temp"], 0.05
        )

        if st.session_state["remember_settings"]:
            _save_settings(
                {
                    "remember_settings": True,
                    "zap_base": st.session_state["zap_base"],
                    "apikey": st.session_state["apikey"],
                    "ollama_base": st.session_state["ollama_base"],
                    "ollama_model": st.session_state["ollama_model"],
                    "ollama_temp": st.session_state["ollama_temp"],
                    "keyword": st.session_state["keyword"],
                    "history_count": st.session_state["history_count"],
                    "bookmarks": st.session_state["bookmarks"],
                }
            )

    # -----------------------------
    # Auto refresh
    # -----------------------------
    if refresh_sec and refresh_sec > 0:
        st.query_params["t"] = str(int(time.time() // refresh_sec))

    # -----------------------------
    # Header
    # -----------------------------
    st.title("Security Demo Dashboard (ZAP Live + AI + Tools)")

    # -----------------------------
    # Fetch ZAP data
    # -----------------------------
    hist_items: List[Dict[str, Any]] = []
    alert_items: List[Dict[str, Any]] = []
    zap_ok = False
    zap_ver = "-"
    last_err: Optional[str] = None

    try:
        z = ZapLiveClient(
            zap_base=st.session_state["zap_base"],
            apikey=st.session_state["apikey"],
            timeout=15,
        )
        zap_ok = True
        zap_ver = z.version()

        raw_msgs = z.messages(count=st.session_state["history_count"])
        for m in raw_msgs:
            method, full_url = reconstruct_url(
                m.get("requestHeader", ""), "http://localhost"
            )
            hist_items.append(
                {
                    "id": m.get("id"),
                    "time": _format_zap_time(m.get("time")),
                    "method": method,
                    "status": m.get("responseCode"),
                    "url": full_url,
                    "rtt": m.get("rtt"),
                    "len": m.get("responseLength"),
                    "requestHeader": m.get("requestHeader", ""),
                    "requestBody": m.get("requestBody", ""),
                    "responseHeader": m.get("responseHeader", ""),
                    "responseBody": m.get("responseBody", ""),
                }
            )

        raw_alerts = z.alerts(count=500)
        for a in raw_alerts:
            alert_items.append(
                {
                    "risk": a.get("risk") or a.get("riskdesc", ""),
                    "name": a.get("alert") or a.get("name", ""),
                    "url": a.get("url", ""),
                    "param": a.get("param", ""),
                    "attack": a.get("attack", ""),
                    "evidence": a.get("evidence", ""),
                    "cweid": a.get("cweid", ""),
                    "wascid": a.get("wascid", ""),
                    "desc": a.get("description", ""),
                    "solution": a.get("solution", ""),
                    "reference": a.get("reference", ""),
                }
            )

        # URL フィルタ
        kw = st.session_state["keyword"].lower().strip()
        if kw:
            hist_items = [h for h in hist_items if kw in _safe_str(h["url"]).lower()]
            alert_items = [a for a in alert_items if kw in _safe_str(a["url"]).lower()]

    except Exception as e:
        last_err = str(e)

    # -----------------------------
    # Top metrics
    # -----------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ZAP接続", "OK" if zap_ok else "NG")
    c2.metric("ZAPバージョン", zap_ver)
    c3.metric("履歴数", str(len(hist_items)))
    c4.metric("アラート数", str(len(alert_items)))

    if last_err:
        st.error(last_err)

    # -----------------------------
    # Top buttons
    # -----------------------------
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("💬 ヘルプAI"):
            st.session_state["open_help_ai"] = True
    with b2:
        if st.button(
            "🤖 選択アラートをAI説明",
            disabled=st.session_state.get("selected_alert") is None,
        ):
            st.session_state["alert_ai_inline"] = True
    with b3:
        if st.button("🧹 アラート解除"):
            st.session_state["selected_alert"] = None
            st.session_state.pop("alert_ai_text", None)

    # -----------------------------
    # Bookmarks
    # -----------------------------
    render_bookmarks_panel(_load_settings, _save_settings)

    # -----------------------------
    # Main tables
    # -----------------------------
    left, right = st.columns([2, 1], gap="large")
    with left:
        render_history_table(hist_items)
    with right:
        render_alerts_table(alert_items)

    # -----------------------------
    # Alert details + AI
    # -----------------------------
    sel = st.session_state.get("selected_alert")
    st.markdown("### 🧾 選択アラート詳細")
    if not sel:
        st.info("アラートを選択してください。")
    else:
        st.write(f"**[{sel['risk']}] {sel['name']}**")
        st.caption(sel["url"])

        with st.expander("Description / Solution", expanded=True):
            st.markdown(sel["desc"] or "(no description)")
            st.markdown(sel["solution"] or "(no solution)")

        if st.button("🧠 このアラートをAI要約"):
            with st.spinner("AI要約中..."):
                st.session_state["alert_ai_text"] = generate_alert_explain(
                    sel,
                    st.session_state["ollama_base"],
                    st.session_state["ollama_model"],
                    st.session_state["ollama_temp"],
                )

        if st.session_state.get("alert_ai_text"):
            st.markdown("#### 🤖 AI要約")
            st.markdown(st.session_state["alert_ai_text"])

    # -----------------------------
    # History details
    # -----------------------------
    render_history_details(hist_items, _load_settings, _save_settings)

    # -----------------------------
    # Report / Tools / AI
    # -----------------------------
    st.divider()
    render_report_ui(hist_items, alert_items)

    st.divider()
    render_tool_ui(st.session_state.get("selected_alert"))

    st.divider()
    render_tool_ai_summary()

    if st.button("🧠 総合リスクAI分析"):
        with st.spinner("分析中..."):
            st.session_state["overall_risk_ai"] = generate_overall_risk_report(
                hist_items, alert_items
            )

    if "overall_risk_ai" in st.session_state:
        st.markdown("## 📊 総合リスク評価")
        st.markdown(st.session_state["overall_risk_ai"])

    # -----------------------------
    # Help AI
    # -----------------------------
    render_help_ai_dialog(
        zap_ok=zap_ok,
        selected_site="(all)",
        hist_len=len(hist_items),
        alert_len=len(alert_items),
        url_filter=st.session_state.get("keyword", ""),
    )
