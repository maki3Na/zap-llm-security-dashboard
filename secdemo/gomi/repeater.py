from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from . import zap_client as zap
from .http_parser import (
    parse_raw_http_request,
    build_raw_http_request,
    extract_query_params,
    extract_body_params_if_form_urlencoded,
    parse_cookie_header,
    build_cookie_header,
    set_query_params,
    set_body_params_form_urlencoded,
    kvlist_to_headers,
)




# ----------------------------
# Helpers
# ----------------------------

def _normalize_kv_rows(rows, name_key="name", value_key="value"):
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        n = str(r.get(name_key, "")).strip()
        v = "" if r.get(value_key) is None else str(r.get(value_key))
        if n == "":
            continue
        out.append({name_key: n, value_key: v})
    return out


def _df_from_kv(rows, cols=("name", "value")):
    if not rows:
        return pd.DataFrame([{cols[0]: "", cols[1]: ""}]).iloc[0:0]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[list(cols)].fillna("")


def _kv_from_df(df, cols=("name", "value")):
    if df is None:
        return []
    rows = df.to_dict(orient="records")
    return _normalize_kv_rows(rows, cols[0], cols[1])


def _safe_set_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default


# ----------------------------
# Raw <-> Form sync
# ----------------------------

def write_form_from_raw(raw_request: str):
    try:
        msg = parse_raw_http_request(raw_request)
    except Exception as e:
        st.error("Rawの解析に失敗しました")
        st.code(str(e))
        return

    # widget key と衝突しないよう、ここは「まだwidget生成前」に呼ぶ前提
    st.session_state.rep_method = msg.method
    st.session_state.rep_url = msg.url
    st.session_state.rep_http_version = msg.http_version
    st.session_state.rep_headers = [{"name": k, "value": v} for k, v in msg.headers]
    st.session_state.rep_body = msg.body or ""

    # パラメータ抽出
    q = extract_query_params(msg.url)
    b = extract_body_params_if_form_urlencoded(msg.headers, msg.body or "")

    cookie_val = ""
    for k, v in msg.headers:
        if k.lower() == "cookie":
            cookie_val = v
            break
    c = parse_cookie_header(cookie_val)

    st.session_state.rep_params_query = q
    st.session_state.rep_params_body = b
    st.session_state.rep_params_cookie = c


def build_raw_from_form() -> str:
    method = st.session_state.get("rep_method", "GET")
    url = st.session_state.get("rep_url", "")
    http_version = st.session_state.get("rep_http_version", "HTTP/1.1")
    body = st.session_state.get("rep_body", "") or ""

    headers_kv = st.session_state.get("rep_headers", [])
    headers = kvlist_to_headers(headers_kv)

    # Query params
    q = st.session_state.get("rep_params_query", [])
    if q:
        url = set_query_params(url, q)

    # Cookie params
    c = st.session_state.get("rep_params_cookie", [])
    if c:
        cookie_header = build_cookie_header(c)
        headers = [(k, v) for (k, v) in headers if k.lower() != "cookie"]
        headers.append(("Cookie", cookie_header))

    # Body params（x-www-form-urlencodedのみ）
    b = st.session_state.get("rep_params_body", [])
    if b:
        body = set_body_params_form_urlencoded(headers, b)

    msg = {
        "method": method,
        "url": url,
        "http_version": http_version,
        "headers": headers,
        "body": body,
    }
    return build_raw_http_request(msg)


# ----------------------------
# UI
# ----------------------------

def render_repeater_panel():
    st.markdown("### 🔁 Repeater（フォーム編集 + 送信）")
    if not st.session_state.get("zap_connected"):
        st.warning("未接続です。ZAP Liveタブで接続テストをしてください。")
        return

    _safe_set_state("zap_repeater_request", "")
    _safe_set_state("zap_repeater_response", "")

    # Repeaterフォームの初期値（widget生成前に用意）
    _safe_set_state("rep_method", "GET")
    _safe_set_state("rep_url", "")
    _safe_set_state("rep_http_version", "HTTP/1.1")
    _safe_set_state("rep_headers", [])
    _safe_set_state("rep_body", "")
    _safe_set_state("rep_params_query", [])
    _safe_set_state("rep_params_body", [])
    _safe_set_state("rep_params_cookie", [])

    st.markdown("#### ① Raw Request")
    st.text_area(
        "Raw Request",
        value=st.session_state.get("zap_repeater_request", ""),
        height=220,
        key="zap_repeater_request",
    )

    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        if st.button("➡ Raw → フォーム同期", use_container_width=True, disabled=(not st.session_state.zap_repeater_request.strip())):
            # ⚠️ widgetが生成された後に rep_method などを書き換えるとエラーになるので
            # ここは rerun を前提に「ボタン押下後に同期→rerun」で確実に安全にする
            raw = st.session_state.zap_repeater_request
            # まず widget を描画する前に同期したいので、フラグを立てる
            st.session_state._do_sync_from_raw = raw
            st.rerun()

    with c2:
        if st.button("⬅ フォーム → Raw生成", use_container_width=True):
            st.session_state.zap_repeater_request = build_raw_from_form()
            st.success("Rawを更新しました")
            st.rerun()

    with c3:
        st.checkbox("followRedirects", value=True, key="rep_follow_redirects")

    # ✅ rerun直後（widget生成前）に同期処理を走らせる
    if st.session_state.get("_do_sync_from_raw"):
        raw = st.session_state.pop("_do_sync_from_raw")
        write_form_from_raw(raw)
        st.success("フォームに反映しました")
        st.rerun()

    st.divider()

    st.markdown("#### ② フォーム編集")
    left, right = st.columns([1.2, 1])

    with left:
        # ✅ 代入しない（keyだけ）
        st.selectbox(
            "Method",
            ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
            index=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"].index(st.session_state.get("rep_method", "GET")),
            key="rep_method",
        )
        st.text_input("URL", value=st.session_state.get("rep_url", ""), key="rep_url")
        st.selectbox("HTTP Version", ["HTTP/1.1", "HTTP/2"], index=0, key="rep_http_version")
        st.text_area("Body", value=st.session_state.get("rep_body", ""), height=180, key="rep_body")

    with right:
        st.markdown("##### Headers")
        headers_df = _df_from_kv(st.session_state.get("rep_headers", []))
        edited_headers_df = st.data_editor(
            headers_df,
            use_container_width=True,
            num_rows="dynamic",
            key="rep_headers_editor",
        )
        st.session_state.rep_headers = _kv_from_df(edited_headers_df)

        st.markdown("##### Params（Query / Body / Cookie）")
        st.caption("※ Query/Body/Cookie は生成時に反映されます（URLやBodyも更新されます）")

        q_df = _df_from_kv(st.session_state.get("rep_params_query", []))
        edited_q_df = st.data_editor(q_df, use_container_width=True, num_rows="dynamic", key="rep_params_query_editor")
        st.session_state.rep_params_query = _kv_from_df(edited_q_df)

        b_df = _df_from_kv(st.session_state.get("rep_params_body", []))
        edited_b_df = st.data_editor(b_df, use_container_width=True, num_rows="dynamic", key="rep_params_body_editor")
        st.session_state.rep_params_body = _kv_from_df(edited_b_df)

        c_df = _df_from_kv(st.session_state.get("rep_params_cookie", []))
        edited_c_df = st.data_editor(c_df, use_container_width=True, num_rows="dynamic", key="rep_params_cookie_editor")
        st.session_state.rep_params_cookie = _kv_from_df(edited_c_df)

    st.divider()

    st.markdown("#### ③ 送信")
    colA, colB = st.columns([1, 2])
    with colA:
        if st.button("🚀 Send（ZAP経由）", use_container_width=True, disabled=(not st.session_state.get("rep_url", "").strip())):
            raw_to_send = build_raw_from_form()
            st.session_state.zap_repeater_request = raw_to_send

            try:
                res = zap.send_request(
                    st.session_state.zap_base,
                    st.session_state.zap_apikey,
                    raw_to_send,
                    follow_redirects=bool(st.session_state.get("rep_follow_redirects", True)),
                )
                payload = res.get("sendRequest", {}) if isinstance(res, dict) else {}
                resp = (payload.get("responseHeader", "") or "") + (payload.get("responseBody", "") or "")
                st.session_state.zap_repeater_response = resp
                st.success("送信しました")
            except Exception as e:
                st.error("送信に失敗しました")
                st.code(str(e))

    with colB:
        st.caption("Tip：History→Message取得→RawをRepeaterへ→フォーム同期→パラメータ編集→Send が最短です。")

    st.markdown("#### ④ Response")
    if st.session_state.get("zap_repeater_response", "").strip():
        st.code(st.session_state.zap_repeater_response[:20000], language="http")
        st.download_button(
            "⬇ Response保存（txt）",
            data=st.session_state.zap_repeater_response.encode("utf-8", errors="ignore"),
            file_name="repeater_response.txt",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        st.info("まだレスポンスがありません。")
