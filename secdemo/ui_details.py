# secdemo/ui_details.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from secdemo.ui_tables import copy_block


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _bookmark_key(item: Dict[str, Any]) -> str:
    return f"{_safe_str(item.get('method'))}|{_safe_str(item.get('url'))}|{_safe_str(item.get('time'))}|{_safe_str(item.get('status'))}"


def render_bookmarks_panel(load_settings_fn, save_settings_fn) -> None:
    with st.expander("📌 Bookmarks（ピン留め）", expanded=False):
        bm_list: List[Dict[str, Any]] = st.session_state.get("bookmarks", []) or []
        if not bm_list:
            st.info("まだピン留めはありません。履歴を選択して「📌 ピン留め」を押してください。")
            return

        df_bm = pd.DataFrame(bm_list)
        show_cols = [c for c in ["time", "method", "status", "url", "note"] if c in df_bm.columns]
        copy_block("Bookmarks", df_bm[show_cols], "bookmarks")

        st.dataframe(df_bm[show_cols], use_container_width=True, height=240)

        if st.button("🗑 全ブックマーク削除", use_container_width=True):
            st.session_state["bookmarks"] = []
            if st.session_state.get("remember_settings", True):
                saved = load_settings_fn()
                saved["bookmarks"] = []
                save_settings_fn(saved)
            st.rerun()


def render_history_details(
    hist_items: List[Dict[str, Any]],
    load_settings_fn,
    save_settings_fn,
) -> None:
    st.divider()
    st.subheader("🔎 詳細（選択した履歴）")

    selected_history_id = st.session_state.get("selected_history_id")
    selected_item: Optional[Dict[str, Any]] = None

    if selected_history_id is not None:
        for it in hist_items:
            if str(it.get("id")) == str(selected_history_id):
                selected_item = it
                break

    if not selected_item:
        st.info("履歴の行をクリックすると、ここにリクエスト/レスポンスが表示されます。")
        return

    bm_key = _bookmark_key(selected_item)
    bm_list = st.session_state.get("bookmarks", []) or []
    already = any(_bookmark_key(bm) == bm_key for bm in bm_list)

    b1, b2, b3 = st.columns([1, 1, 2], gap="small")
    with b1:
        if st.button("📌 ピン留め", use_container_width=True, disabled=already):
            bm = {
                "time": selected_item.get("time", ""),
                "method": selected_item.get("method", ""),
                "status": selected_item.get("status", ""),
                "url": selected_item.get("url", ""),
                "note": "",
                "requestHeader": selected_item.get("requestHeader", ""),
                "requestBody": selected_item.get("requestBody", ""),
                "responseHeader": selected_item.get("responseHeader", ""),
                "responseBody": selected_item.get("responseBody", ""),
            }
            st.session_state["bookmarks"] = [bm] + bm_list
            if st.session_state.get("remember_settings", True):
                saved = load_settings_fn()
                saved["bookmarks"] = st.session_state["bookmarks"]
                save_settings_fn(saved)
            st.success("ピン留めしました。上の Bookmarks を開くと確認できます。")

    with b2:
        if st.button("🧹 ピン留め解除", use_container_width=True, disabled=not already):
            st.session_state["bookmarks"] = [bm for bm in bm_list if _bookmark_key(bm) != bm_key]
            if st.session_state.get("remember_settings", True):
                saved = load_settings_fn()
                saved["bookmarks"] = st.session_state["bookmarks"]
                save_settings_fn(saved)
            st.success("解除しました。")

    with b3:
        st.caption("※ブックマークはローカル保存（設定ONの場合）されます。")

    d1, d2 = st.columns(2, gap="large")
    with d1:
        st.markdown("### Request")
        st.caption(_safe_str(selected_item.get("url")))
        with st.expander("Request Header", expanded=True):
            st.code(_safe_str(selected_item.get("requestHeader")), language="http")
        with st.expander("Request Body", expanded=False):
            st.code(_safe_str(selected_item.get("requestBody")), language="")

    with d2:
        st.markdown("### Response")
        with st.expander("Response Header", expanded=True):
            st.code(_safe_str(selected_item.get("responseHeader")), language="http")
        with st.expander("Response Body", expanded=False):
            st.code(_safe_str(selected_item.get("responseBody")), language="")
