# secdemo/ui_tools.py
from __future__ import annotations

import subprocess
from typing import Optional, Tuple

import streamlit as st


def _host_from_url(url: str) -> str:
    url = (url or "").strip()
    if "://" in url:
        try:
            return url.split("/")[2]
        except Exception:
            return url
    return url


def _run(cmd: list[str], timeout_sec: int = 300) -> Tuple[str, str, int]:
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    out = (p.stdout or "") + ("\n" if p.stdout and p.stderr else "") + (p.stderr or "")
    return out, " ".join(cmd), p.returncode


def _ensure_tools_state() -> None:
    st.session_state.setdefault("tool_allow_run", False)
    st.session_state.setdefault("sqlmap_output", "")
    st.session_state.setdefault("sqlmap_cmd", "")
    st.session_state.setdefault("nmap_output", "")
    st.session_state.setdefault("nmap_cmd", "")


# -------------------------
# sqlmap（安全モード）
# -------------------------
def _sqlmap_cmd(url: str, param: Optional[str]) -> list[str]:
    cmd = [
        "sqlmap",
        "-u",
        url,
        "--batch",
        "--level=1",
        "--risk=1",
        "--random-agent",
        "--timeout=10",
        "--retries=1",
        "--banner",
    ]
    if param:
        cmd += ["-p", param]
    return cmd


# -------------------------
# nmap（安全モード）
# -------------------------
def _nmap_cmd(target: str, top_ports: int = 100, version_detect: bool = True) -> list[str]:
    cmd = ["nmap", "-sT", "-Pn", f"--top-ports={int(top_ports)}"]
    if version_detect:
        cmd += ["-sV"]
    cmd += [target]
    return cmd


def render_tool_ui(selected_alert) -> None:
    """
    sqlmap / nmap を UI 内から実行。
    - 実行前に同意チェック必須（面接で強い）
    - コマンド表示（透明性）
    - 出力は session_state に保持（AI要約→レポート連携の素材）
    """
    _ensure_tools_state()

    st.subheader("🛠 外部ツール（安全モード）")

    if not selected_alert:
        st.info("アラートを1件選択してください。")
        return

    url = (selected_alert.get("url") or "").strip()
    param = (selected_alert.get("param") or "").strip()

    # 同意チェック（必須）
    st.session_state["tool_allow_run"] = st.checkbox(
        "✅ 許可を得た対象に対してのみ実行します（同意）",
        value=bool(st.session_state.get("tool_allow_run", False)),
        help="面接で説明しやすい “安全設計” として入れています。",
    )

    # ---- sqlmap ----
    with st.expander("🛠 sqlmap（読み取り専用）", expanded=False):
        st.caption("※ 低risk/low level でのみ実行（安全寄り）")
        st.code(f"Target URL: {url}\nParam: {param or '(auto)'}")

        cmd = _sqlmap_cmd(url, param if param else None)
        st.code("CMD: " + " ".join(cmd))

        run_disabled = (not st.session_state["tool_allow_run"]) or (not url)
        if st.button("▶ sqlmap 実行", use_container_width=True, disabled=run_disabled, key="run_sqlmap"):
            with st.spinner("sqlmap 実行中..."):
                out, cmd_str, rc = _run(cmd, timeout_sec=300)
                st.session_state["sqlmap_output"] = out
                st.session_state["sqlmap_cmd"] = cmd_str
                st.session_state["sqlmap_rc"] = rc

        if st.session_state.get("sqlmap_output"):
            st.text_area("sqlmap output", st.session_state["sqlmap_output"], height=280)
            st.caption(f"return code: {st.session_state.get('sqlmap_rc')}")

    # ---- nmap ----
    with st.expander("🛠 nmap（ポート・サービス検出）", expanded=False):
        target = _host_from_url(url)
        st.code(f"Target host: {target}")

        top_ports = st.slider("top ports", 10, 1000, 100, 10, key="nmap_top_ports")
        version_detect = st.checkbox("サービス/バージョン検出（-sV）", value=True, key="nmap_sv")

        cmd = _nmap_cmd(target, top_ports=top_ports, version_detect=version_detect)
        st.code("CMD: " + " ".join(cmd))

        run_disabled = (not st.session_state["tool_allow_run"]) or (not target)
        if st.button("▶ nmap 実行", use_container_width=True, disabled=run_disabled, key="run_nmap"):
            with st.spinner("nmap 実行中..."):
                out, cmd_str, rc = _run(cmd, timeout_sec=300)
                st.session_state["nmap_output"] = out
                st.session_state["nmap_cmd"] = cmd_str
                st.session_state["nmap_rc"] = rc

        if st.session_state.get("nmap_output"):
            st.text_area("nmap output", st.session_state["nmap_output"], height=280)
            st.caption(f"return code: {st.session_state.get('nmap_rc')}")
