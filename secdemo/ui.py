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

# 互換：render_sqlmap_ui がある場合だけ使う（無いなら render_tool_ui を使う構成でもOK）
try:
    from secdemo.ui_tools import render_sqlmap_ui  # type: ignore
except Exception:
    render_sqlmap_ui = None  # type: ignore

from secdemo.ui_tools import render_tool_ui
from secdemo.ui_tool_ai import render_tool_ai_summary


# =============================
# Settings persistence (local file)
# =============================
def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _settings_path() -> str:
    root = _project_root()
    data_dir = os.path.join(root, "secdemo_data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "ui_settings.json")


def _load_settings() -> Dict[str, Any]:
    p = _settings_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_settings(d: Dict[str, Any]) -> None:
    p = _settings_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _format_zap_time(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if s.isdigit():
        try:
            n = int(s)
            # ZAPによってはms epochが来ることがある
            if n > 10_000_000_000:
                dt = datetime.fromtimestamp(n / 1000.0)
            else:
                dt = datetime.fromtimestamp(n)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s
    return s


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _normalize_alert(a: Dict[str, Any]) -> Dict[str, Any]:
    """
    UI側が参照するキーを必ず持つように正規化（KeyError防止）
    """
    base = {
        "risk": "",
        "name": "",
        "url": "",
        "param": "",
        "attack": "",
        "evidence": "",
        "cweid": "",
        "wascid": "",
        "desc": "",
        "solution": "",
        "reference": "",
    }
    if not a:
        return base
    base.update({k: a.get(k, base.get(k, "")) for k in base.keys()})
    return base


def render_app() -> None:
    # -----------------------------
    # Initial load
    # -----------------------------
    if "settings_loaded" not in st.session_state:
        saved = _load_settings()
        st.session_state["remember_settings"] = saved.get("remember_settings", True)
        st.session_state["zap_base"] = saved.get("zap_base", "http://127.0.0.1:8080")
        st.session_state["apikey"] = saved.get("apikey", "")
        st.session_state["ollama_base"] = saved.get("ollama_base", "http://127.0.0.1:11434")
        st.session_state["ollama_model"] = saved.get("ollama_model", "")
        st.session_state["ollama_temp"] = float(saved.get("ollama_temp", 0.2))
        st.session_state["keyword"] = saved.get("keyword", "")
        st.session_state["bookmarks"] = saved.get("bookmarks", []) or []
        st.session_state["selected_alert"] = None
        st.session_state["selected_history_id"] = None
        st.session_state["history_count"] = int(saved.get("history_count", 200))
        st.session_state["settings_loaded"] = True

    # -----------------------------
    # Sidebar
    # -----------------------------
    with st.sidebar:
        st.markdown("## 🔌 ZAP接続")

        remember = st.checkbox(
            "設定を保存（ローカル）",
            value=bool(st.session_state.get("remember_settings", True)),
            help="ONにするとAPIキー/モデルなどをローカルJSONに保存します（個人PC前提）。",
        )
        st.session_state["remember_settings"] = remember

        st.session_state["zap_base"] = st.text_input(
            "ZAP Base URL",
            value=st.session_state.get("zap_base", "http://127.0.0.1:8080"),
        )
        st.session_state["apikey"] = st.text_input(
            "ZAP API Key",
            value=st.session_state.get("apikey", ""),
            type="password",
        )

        st.markdown("## 🔄 更新")
        refresh_sec = st.selectbox("Auto refresh (sec)", [0, 2, 5, 10], index=2)

        history_count = st.slider(
            "History rows",
            50,
            500,
            int(st.session_state.get("history_count", 200)),
            step=50,
        )
        st.session_state["history_count"] = history_count

        st.markdown("## 🔎 フィルタ")
        st.session_state["keyword"] = st.text_input(
            "URL contains",
            value=st.session_state.get("keyword", ""),
            placeholder="/login /api /admin など",
        )

        st.markdown("## 🤖 AI設定")
        st.session_state["ollama_base"] = st.text_input(
            "Ollama Base URL",
            value=st.session_state.get("ollama_base", "http://127.0.0.1:11434"),
        )

        # ✅ モデル一覧を取得して selectbox 化（失敗時は手入力にフォールバック）
        models: List[str] = []
        try:
            client = OllamaChatClient(st.session_state["ollama_base"], timeout=10)
            models = client.list_models()
        except Exception:
            models = []

        saved_model = st.session_state.get("ollama_model", "")
        if models:
            if saved_model not in models:
                saved_model = models[0]
                st.session_state["ollama_model"] = saved_model

            st.session_state["ollama_model"] = st.selectbox(
                "Model",
                options=models,
                index=models.index(saved_model),
                help="Ollamaに存在するモデルのみ表示します（デモ中の事故防止）",
            )
        else:
            st.session_state["ollama_model"] = st.text_input(
                "Model（手入力）",
                value=saved_model or "gemma2:9b-instruct-q5_K_M",
                help="モデル一覧が取得できない場合のみ手入力になります",
            )

        st.session_state["ollama_temp"] = st.slider(
            "Temperature",
            0.0,
            1.0,
            float(st.session_state.get("ollama_temp", 0.2)),
            0.05,
        )

        if remember:
            _save_settings(
                {
                    "remember_settings": True,
                    "zap_base": st.session_state["zap_base"],
                    "apikey": st.session_state["apikey"],
                    "ollama_base": st.session_state["ollama_base"],
                    "ollama_model": st.session_state["ollama_model"],
                    "ollama_temp": st.session_state.get("ollama_temp", 0.2),
                    "keyword": st.session_state.get("keyword", ""),
                    "bookmarks": st.session_state.get("bookmarks", []),
                    "history_count": st.session_state.get("history_count", 200),
                }
            )

    # -----------------------------
    # Auto refresh（st.query_params）
    # -----------------------------
    if refresh_sec and refresh_sec > 0:
        st.query_params["t"] = str(int(time.time() // refresh_sec))

    # -----------------------------
    # Header
    # -----------------------------
    st.title("Security Demo Dashboard (ZAP Live + Report + Quick Checks)")

    # -----------------------------
    # Fetch data from ZAP
    # -----------------------------
    zap_ok = False
    zap_ver = "-"
    selected_site = "(all)"
    sites: List[str] = ["(all)"]

    hist_items: List[Dict[str, Any]] = []
    alert_items: List[Dict[str, Any]] = []
    last_err: Optional[str] = None

    try:
        z = ZapLiveClient(
            zap_base=st.session_state["zap_base"],
            apikey=st.session_state["apikey"],
            timeout=15,
        )
        zap_ver = z.version()
        zap_ok = True

        try:
            sites = ["(all)"] + z.sites()
        except Exception:
            sites = ["(all)"]

        selected_site = st.sidebar.selectbox("対象サイト", options=sites, index=0)

        # History
        try:
            raw_msgs = z.messages(baseurl=None if selected_site == "(all)" else selected_site, count=history_count)
        except Exception:
            raw_msgs = z.messages(count=history_count)

        fallback = selected_site if selected_site != "(all)" else "http://localhost"
        for m in raw_msgs:
            req_h = m.get("requestHeader", "") or ""
            method, full_url = reconstruct_url(req_h, fallback_base=fallback)
            hist_items.append(
                {
                    "id": m.get("id"),
                    "time": _format_zap_time(m.get("time")),
                    "method": method,
                    "status": m.get("responseCode"),
                    "url": full_url,
                    "rtt": m.get("rtt"),
                    "len": m.get("responseLength"),
                    "requestHeader": req_h,
                    "requestBody": m.get("requestBody", "") or "",
                    "responseHeader": m.get("responseHeader", "") or "",
                    "responseBody": m.get("responseBody", "") or "",
                }
            )

        # Alerts
        try:
            raw_alerts = z.alerts(baseurl=None if selected_site == "(all)" else selected_site, count=500)
        except Exception:
            raw_alerts = z.alerts(count=500)

        for a in raw_alerts:
            alert_items.append(
                _normalize_alert(
                    {
                        "risk": a.get("risk") or a.get("riskdesc") or "",
                        "name": a.get("alert") or a.get("name") or "",
                        "url": a.get("url") or "",
                        "param": a.get("param") or "",
                        "attack": a.get("attack") or "",
                        "evidence": a.get("evidence") or "",
                        "cweid": a.get("cweid") or "",
                        "wascid": a.get("wascid") or "",
                        "desc": a.get("description") or "",
                        "solution": a.get("solution") or "",
                        "reference": a.get("reference") or "",
                    }
                )
            )

        # URL contains filter（維持）
        kw = (st.session_state.get("keyword") or "").strip().lower()
        if kw:
            hist_items = [x for x in hist_items if kw in _safe_str(x.get("url")).lower()]
            alert_items = [x for x in alert_items if kw in _safe_str(x.get("url")).lower()]

    except Exception as e:
        last_err = str(e)

    # -----------------------------
    # Top metrics
    # -----------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ZAP接続", "OK" if zap_ok else "NG")
    c2.metric("ZAPバージョン", zap_ver)
    c3.metric("サイト", selected_site)
    c4.metric("履歴項目", str(len(hist_items)))

    if last_err:
        st.error(f"ZAP取得エラー: {last_err}")

    # -----------------------------
    # Top buttons
    # -----------------------------
    b1, b2, b3 = st.columns([1, 1, 1], gap="small")
    with b1:
        if st.button("💬 ヘルプAI", use_container_width=True):
            st.session_state["open_help_ai"] = True
    with b2:
        if st.button(
            "🤖 選択アラートをAIで説明",
            use_container_width=True,
            disabled=st.session_state.get("selected_alert") is None,
        ):
            st.session_state["alert_ai_inline"] = True
    with b3:
        if st.button("🧹 アラート選択解除", use_container_width=True):
            st.session_state["selected_alert"] = None
            st.session_state.pop("alert_ai_text", None)
            st.rerun()

    # -----------------------------
    # Bookmarks panel
    # -----------------------------
    render_bookmarks_panel(_load_settings, _save_settings)

    # -----------------------------
    # Main tables (History / Alerts)
    # -----------------------------
    left, right = st.columns([2, 1], gap="large")
    with left:
        render_history_table(hist_items)

    with right:
        render_alerts_table(alert_items)

        # ✅ アラート詳細パネル（右側に常時）
        sel_raw = st.session_state.get("selected_alert")
        sel = _normalize_alert(sel_raw) if sel_raw else None

        st.markdown("### 🧾 選択アラート詳細")

        if not sel_raw:
            st.info("右の表からアラートを1件選択してください。")
        else:
            st.write(f"**[{sel.get('risk','')}] {sel.get('name','')}**")
            st.caption(sel.get("url", ""))

            with st.expander("Description / Solution", expanded=True):
                st.markdown(sel.get("desc") or "(no description)")
                st.markdown("---")
                st.markdown(sel.get("solution") or "(no solution)")

            with st.expander("Evidence / IDs / Reference", expanded=False):
                st.markdown(f"- Param: `{sel.get('param','')}`")
                st.markdown(f"- CWE: `{sel.get('cweid','')}` / WASC: `{sel.get('wascid','')}`")
                st.markdown(f"- Evidence: `{sel.get('evidence','')}`")
                st.markdown(f"- Reference: {sel.get('reference','') or '(none)'}")

            # ✅ AI要約を「詳細内に統合」
            if st.button("🧠 このアラートをAI要約（詳細に表示）", use_container_width=True):
                with st.spinner("AIで要約中..."):
                    text = generate_alert_explain(
                        alert=sel,
                        ollama_base=st.session_state["ollama_base"],
                        model=st.session_state["ollama_model"],
                        temperature=float(st.session_state.get("ollama_temp", 0.2)),
                    )
                st.session_state["alert_ai_text"] = text

            if st.session_state.get("alert_ai_text"):
                st.markdown("#### 🤖 AI要約")
                st.markdown(st.session_state["alert_ai_text"])

    # -----------------------------
    # Details（History）
    # -----------------------------
    render_history_details(hist_items, _load_settings, _save_settings)

    # -----------------------------
    # Report UI
    # -----------------------------
    st.divider()
    render_report_ui(hist_items, alert_items)

    # -----------------------------
    # External tools UI
    # -----------------------------
    st.divider()

    # 旧sqlmap専用UIがある場合は表示（互換）
    if render_sqlmap_ui is not None:
        render_sqlmap_ui(st.session_state.get("selected_alert"))

    # 新ツール統合UI
    render_tool_ui(st.session_state.get("selected_alert"))

    # ツール結果のAI要約
    st.divider()
    render_tool_ai_summary()

    # -----------------------------
    # Overall risk AI
    # -----------------------------
    st.divider()
    if st.button("🧠 総合リスクAI分析", use_container_width=True):
        with st.spinner("AIが全体を分析しています..."):
            st.session_state["overall_risk_ai"] = generate_overall_risk_report(hist_items, alert_items)

    if "overall_risk_ai" in st.session_state:
        st.markdown("## 📊 総合リスク評価（AI）")
        st.markdown(st.session_state["overall_risk_ai"])

    # -----------------------------
    # Help AI dialog
    # -----------------------------
    render_help_ai_dialog(
        zap_ok=zap_ok,
        selected_site=selected_site,
        hist_len=len(hist_items),
        alert_len=len(alert_items),
        url_filter=st.session_state.get("keyword", ""),
    )
