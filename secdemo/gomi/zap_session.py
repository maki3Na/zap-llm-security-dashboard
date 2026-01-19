# secdemo/zap_session.py
from __future__ import annotations
from typing import Dict, Any
from .zap_client import zap_json_get

import streamlit as st
from secdemo.ui import render_app

st.set_page_config(
    page_title="Security Demo (ZAP + LLM)",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_app()


def add_include_regex(base: str, apikey: str, regex: str) -> Dict[str, Any]:
    # core/action/includeInContext? は context API のため環境差が出る
    # まずは core/action/excludeFromProxy/includeInProxy などに頼らず、
    # レポートや絞り込み用にregexをユーザーが管理できるようにする。
    return {"ok": True, "message": "このアプリ側で include regex を保持します（ZAP側への反映は次段階で対応）。", "regex": regex}

def add_exclude_regex(base: str, apikey: str, regex: str) -> Dict[str, Any]:
    return {"ok": True, "message": "このアプリ側で exclude regex を保持します（ZAP側への反映は次段階で対応）。", "regex": regex}

def get_mode(base: str, apikey: str) -> str:
    try:
        m = zap_json_get(base, "/JSON/core/view/mode/", apikey, timeout=8)
        return m.get("mode","")
    except Exception:
        return ""
