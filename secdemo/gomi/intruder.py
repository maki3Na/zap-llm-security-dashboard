import re
import time
from typing import List, Dict, Any

import streamlit as st

from . import zap_client as zap
from .http_parser import parse_raw_http_request, build_raw_http_request



def _extract_status_and_length(raw_response: str):
    status = ""
    length = 0
    if not raw_response:
        return status, length
    # status
    m = re.search(r"HTTP/\d\.\d\s+(\d+)", raw_response)
    if m:
        status = m.group(1)
    # length: body length (rough)
    parts = raw_response.split("\r\n\r\n", 1)
    body = parts[1] if len(parts) == 2 else ""
    length = len(body.encode("utf-8", errors="ignore"))
    return status, length


def _regex_hits(raw_response: str, patterns: List[str]) -> Dict[str, bool]:
    hits = {}
    text = raw_response or ""
    for p in patterns:
        p = (p or "").strip()
        if not p:
            continue
        try:
            hits[p] = bool(re.search(p, text, flags=re.IGNORECASE))
        except re.error:
            hits[p] = False
    return hits


def render_intruder_panel():
    st.markdown("### 🎯 Intruder（簡易）")
    if not st.session_state.get("zap_connected"):
        st.warning("未接続です。ZAP Liveタブで接続テストをしてください。")
        return

    # state init
    if "intruder_results" not in st.session_state:
        st.session_state.intruder_results = []

    st.caption("指定パラメータにpayloadを流し込み → 連続送信 → status/size/regex差分を表示します。")

    raw = st.text_area(
        "Base Raw Request（RepeaterのRawを貼り付け推奨）",
        value=st.session_state.get("zap_repeater_request", ""),
        height=220,
        key="intruder_base_raw",
    )

    param_name = st.text_input("対象パラメータ名（query/body/cookieのいずれか）", value="q", key="intruder_param_name")

    payloads_text = st.text_area(
        "Payload list（1行1つ）",
        value="1\n' OR '1'='1\n<svg/onload=alert(1)>\n../../../../etc/passwd",
        height=160,
        key="intruder_payloads",
    )

    patterns_text = st.text_input(
        "差分検出regex（カンマ区切り）例: error, sql, warning, root:x",
        value="error, sql, warning, root:x",
        key="intruder_regex_patterns",
    )
    patterns = [p.strip() for p in patterns_text.split(",") if p.strip()]

    follow = st.checkbox("followRedirects", value=True, key="intruder_follow_redirects")
    delay_ms = st.slider("送信間隔(ms)", 0, 1000, 50, 50, key="intruder_delay_ms")

    def build_mutated_raw(base_raw: str, name: str, value: str) -> str:
        msg = parse_raw_http_request(base_raw)
        # URL query
        if "?" in msg.url and name:
            from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
            u = urlsplit(msg.url)
            qs = dict(parse_qsl(u.query, keep_blank_values=True))
            if name in qs:
                qs[name] = value
                msg.url = urlunsplit((u.scheme, u.netloc, u.path, urlencode(qs, doseq=True), u.fragment))

        # Body (x-www-form-urlencoded)
        ctype = ""
        for k, v in msg.headers:
            if k.lower() == "content-type":
                ctype = v
        if name and ctype.lower().startswith("application/x-www-form-urlencoded") and msg.body:
            from urllib.parse import parse_qsl, urlencode
            d = dict(parse_qsl(msg.body, keep_blank_values=True))
            if name in d:
                d[name] = value
                msg.body = urlencode(d, doseq=True)

        # Cookie
        for i, (k, v) in enumerate(msg.headers):
            if k.lower() == "cookie":
                from .http_parser import parse_cookie_header, build_cookie_header
                ck = parse_cookie_header(v)
                found = False
                for item in ck:
                    if item.get("name") == name:
                        item["value"] = value
                        found = True
                if found:
                    msg.headers[i] = (k, build_cookie_header(ck))

        return build_raw_http_request({
            "method": msg.method,
            "url": msg.url,
            "http_version": msg.http_version,
            "headers": msg.headers,
            "body": msg.body or "",
        })

    if st.button("▶ Intruder 実行", use_container_width=True, disabled=(not raw.strip() or not param_name.strip())):
        payloads = [p for p in payloads_text.splitlines() if p.strip()]
        st.session_state.intruder_results = []

        # baseline（payload無しの状態）
        baseline_resp = ""
        try:
            res0 = zap.send_request(st.session_state.zap_base, st.session_state.zap_apikey, raw, follow_redirects=bool(follow))
            payload0 = res0.get("sendRequest", {}) if isinstance(res0, dict) else {}
            baseline_resp = (payload0.get("responseHeader", "") or "") + (payload0.get("responseBody", "") or "")
        except Exception as e:
            st.error("Baseline送信に失敗しました")
            st.code(str(e))
            return

        base_status, base_len = _extract_status_and_length(baseline_resp)
        base_hits = _regex_hits(baseline_resp, patterns)

        for idx, p in enumerate(payloads, 1):
            mutated = build_mutated_raw(raw, param_name.strip(), p)
            try:
                res = zap.send_request(st.session_state.zap_base, st.session_state.zap_apikey, mutated, follow_redirects=bool(follow))
                payload = res.get("sendRequest", {}) if isinstance(res, dict) else {}
                resp = (payload.get("responseHeader", "") or "") + (payload.get("responseBody", "") or "")
            except Exception as e:
                resp = f"ERROR: {e}"

            stt, ln = _extract_status_and_length(resp)
            hits = _regex_hits(resp, patterns)

            st.session_state.intruder_results.append({
                "no": idx,
                "param": param_name.strip(),
                "payload": p,
                "status": stt,
                "length": ln,
                "d_status": (stt != base_status),
                "d_length": (ln != base_len),
                "delta_length": (ln - base_len),
                "regex_hits": hits,
                "regex_diff": {k: (hits.get(k) != base_hits.get(k)) for k in hits.keys()},
            })

            if delay_ms:
                time.sleep(delay_ms / 1000.0)

        st.success("Intruder 完了")

    # 表示
    if st.session_state.intruder_results:
        st.markdown("#### 結果（差分）")

        rows = []
        for r in st.session_state.intruder_results:
            diff_regex = [k for k, v in (r.get("regex_diff") or {}).items() if v]
            hit_regex = [k for k, v in (r.get("regex_hits") or {}).items() if v]

            rows.append({
                "no": r["no"],
                "payload": r["payload"],
                "status": r["status"],
                "len": r["length"],
                "Δlen": r["delta_length"],
                "statusΔ": "Y" if r["d_status"] else "",
                "lenΔ": "Y" if r["d_length"] else "",
                "hit(regex)": ", ".join(hit_regex)[:80],
                "diff(regex)": ", ".join(diff_regex)[:80],
            })

        st.dataframe(rows, use_container_width=True, hide_index=True)

        pick = st.number_input("詳細を見る No", min_value=1, max_value=len(st.session_state.intruder_results), value=1, step=1)
        item = st.session_state.intruder_results[int(pick) - 1]
        st.json(item)
    else:
        st.info("まだIntruder結果がありません。")
