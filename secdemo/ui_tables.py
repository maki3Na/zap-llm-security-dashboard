# secdemo/ui_tables.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode


def _risk_rank(text: str) -> int:
    s = (text or "").lower()
    if "high" in s:
        return 3
    if "medium" in s:
        return 2
    if "low" in s:
        return 1
    if "info" in s:
        return 0
    return -1


def _risk_label(text: str) -> str:
    s = (text or "").lower()
    if "high" in s:
        return "High"
    if "medium" in s:
        return "Medium"
    if "low" in s:
        return "Low"
    if "info" in s:
        return "Info"
    return "Other"


def _selected_rows_as_list(grid_resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    sel = grid_resp.get("selected_rows")
    if sel is None:
        return []
    if isinstance(sel, pd.DataFrame):
        if sel.empty:
            return []
        return sel.to_dict(orient="records")
    if isinstance(sel, list):
        return sel
    return []


def _df_to_tsv(df: pd.DataFrame) -> str:
    return df.to_csv(sep="\t", index=False)


def copy_block(title: str, df: pd.DataFrame, key_prefix: str, selected_df: Optional[pd.DataFrame] = None) -> None:
    if df is None or df.empty:
        return

    c1, c2, c3, c4 = st.columns([1.0, 1.0, 1.0, 5.0], gap="small")
    with c1:
        st.download_button(
            "⬇ CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"{key_prefix}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "⬇ TSV",
            data=_df_to_tsv(df).encode("utf-8"),
            file_name=f"{key_prefix}.tsv",
            mime="text/tab-separated-values",
            use_container_width=True,
        )
    with c3:
        with st.popover("📋 Copy", use_container_width=True):
            st.caption("全選択 → Ctrl+C（Excel貼り付けOK）")
            st.text_area(
                f"{title} TSV",
                value=_df_to_tsv(df),
                height=240,
                key=f"{key_prefix}_copy_all",
            )
    with c4:
        if selected_df is not None and not selected_df.empty:
            with st.popover("🎯 選択だけCopy"):
                st.caption("選択行のみ")
                st.text_area(
                    f"{title} Selected TSV",
                    value=_df_to_tsv(selected_df),
                    height=160,
                    key=f"{key_prefix}_copy_selected",
                )
        else:
            st.caption("※ 行を選択すると「選択だけCopy」が使えます")


def render_history_table(hist_items: List[Dict[str, Any]]) -> None:
    st.subheader("📜 履歴（Messages）")
    df_hist = pd.DataFrame(hist_items)

    if df_hist.empty:
        st.info("履歴が空です。ZAPプロキシ経由で通信が流れているか確認してください。")
        return

    show_cols = ["time", "method", "status", "url", "rtt", "len", "id"]
    for c in show_cols:
        if c not in df_hist.columns:
            df_hist[c] = ""

    df_show = df_hist[show_cols].copy()

    gb = GridOptionsBuilder.from_dataframe(df_show)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)
    gb.configure_grid_options(enableRangeSelection=True, enableCellTextSelection=True)
    gb.configure_column("url", flex=5, min_width=340)
    gb.configure_column("id", hide=True)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=25)

    grid = AgGrid(
        df_show,
        gridOptions=gb.build(),
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True,
        height=420,
        enable_enterprise_modules=False,
        key="history_grid",
    )

    sel = _selected_rows_as_list(grid)
    selected_df = None
    if sel:
        selected_id = sel[0].get("id")
        st.session_state["selected_history_id"] = selected_id
        try:
            selected_df = df_show[df_show["id"].astype(str) == str(selected_id)].drop(columns=["id"], errors="ignore")
        except Exception:
            selected_df = None

    copy_block("History", df_show.drop(columns=["id"], errors="ignore"), "history", selected_df)


def render_alerts_table(alert_items: List[Dict[str, Any]]) -> None:
    st.subheader("🚨 アラート")
    df_alert = pd.DataFrame(alert_items)

    # リスクカード
    if df_alert.empty:
        cH, cM, cL, cI = st.columns([1, 1, 1, 1], gap="small")
        cH.metric("High", "0")
        cM.metric("Med", "0")
        cL.metric("Low", "0")
        cI.metric("Info", "0")
        st.info("アラートがありません（または取得できません）。")
        return

    df_alert["risk_label"] = df_alert["risk"].apply(_risk_label)
    counts = df_alert["risk_label"].value_counts().to_dict()
    cH, cM, cL, cI = st.columns([1, 1, 1, 1], gap="small")
    cH.metric("High", str(int(counts.get("High", 0))))
    cM.metric("Med", str(int(counts.get("Medium", 0))))
    cL.metric("Low", str(int(counts.get("Low", 0))))
    cI.metric("Info", str(int(counts.get("Info", 0))))

    # 表
    df_alert["__risk"] = df_alert["risk"].apply(_risk_rank)

    show_cols = ["risk", "name", "url", "param", "__risk"]
    for c in show_cols:
        if c not in df_alert.columns:
            df_alert[c] = ""

    df_show = df_alert[show_cols].copy()

    gb = GridOptionsBuilder.from_dataframe(df_show)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)
    gb.configure_grid_options(enableRangeSelection=True, enableCellTextSelection=True)
    gb.configure_column("risk", flex=1, min_width=110)
    gb.configure_column("name", flex=3, min_width=220)
    gb.configure_column("param", flex=1, min_width=120)
    gb.configure_column("url", flex=4, min_width=260)
    gb.configure_column("__risk", hide=True)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)

    grid = AgGrid(
        df_show.sort_values("__risk", ascending=False),
        gridOptions=gb.build(),
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True,
        height=420,
        enable_enterprise_modules=False,
        key="alerts_grid",
    )

    sel = _selected_rows_as_list(grid)

    # ✅ 選択できたときだけ state を更新（消さない）
    selected_alert_df = None
    if sel:
        cand = sel[0]
        st.session_state["selected_alert"] = cand  # 最低限はこれでOK（必要なら元データへ復元はui.py側で実施）

        try:
            r = str(cand.get("risk", ""))
            n = str(cand.get("name", ""))
            u = str(cand.get("url", ""))
            p = str(cand.get("param", ""))
            selected_alert_df = (
                df_show[
                    (df_show["risk"].astype(str) == r)
                    & (df_show["name"].astype(str) == n)
                    & (df_show["url"].astype(str) == u)
                    & (df_show["param"].astype(str) == p)
                ]
                .drop(columns=["__risk"], errors="ignore")
            )
        except Exception:
            selected_alert_df = None

    sel_state = st.session_state.get("selected_alert")
    if sel_state:
        st.caption(f"Selected: [{sel_state.get('risk','')}] {sel_state.get('name','')}")
    else:
        st.caption("Selected: (none)")

    copy_block("Alerts", df_show.drop(columns=["__risk"], errors="ignore"), "alerts", selected_alert_df)
