import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from .utils import now_str

import streamlit as st
from secdemo.ui import render_app

st.set_page_config(
    page_title="Security Demo (ZAP + LLM)",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_app()


def which_or_none(cmd: str) -> Optional[str]:
    return shutil.which(cmd)

def run_command(args: List[str], timeout_sec: int) -> Dict[str, Any]:
    started = now_str()
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
        ended = now_str()
        return {
            "tool": args[0],
            "command": args,
            "started_at": started,
            "ended_at": ended,
            "stdout": p.stdout or "",
            "stderr": p.stderr or "",
            "returncode": p.returncode,
        }
    except subprocess.TimeoutExpired as e:
        ended = now_str()
        return {
            "tool": args[0],
            "command": args,
            "started_at": started,
            "ended_at": ended,
            "stdout": (e.stdout or "") if hasattr(e, "stdout") else "",
            "stderr": f"TIMEOUT: {timeout_sec}s\n" + ((e.stderr or "") if hasattr(e, "stderr") else ""),
            "returncode": -1,
        }
    except FileNotFoundError:
        return {
            "tool": args[0],
            "command": args,
            "started_at": started,
            "ended_at": started,
            "stdout": "",
            "stderr": f"COMMAND NOT FOUND: {args[0]}（PATHに存在しません）",
            "returncode": -2,
        }

def parse_nmap_grepable(text: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if "Ports:" not in line:
            continue
        m = re.search(r"Host:\s+(\S+)", line)
        host = m.group(1) if m else ""
        ports_part = line.split("Ports:", 1)[1].strip()
        for ent in ports_part.split(","):
            ent = ent.strip()
            parts = ent.split("/")
            if len(parts) < 5:
                continue
            port = parts[0].strip()
            state = parts[1].strip()
            proto = parts[2].strip()
            service = parts[4].strip() if len(parts) >= 5 else ""
            version = parts[6].strip() if len(parts) >= 7 else ""
            rows.append({
                "host": host,
                "port": port,
                "proto": proto,
                "state": state,
                "service": service,
                "version": version,
            })
    return rows

def build_ai_input(scan_results: List[Dict[str, Any]], nmap_ports_table: List[Dict[str, Any]]) -> str:
    blocks = []
    if nmap_ports_table:
        open_rows = [r for r in nmap_ports_table if r.get("state") == "open"]
        blocks.append("## Parsed Nmap Ports (open only)")
        blocks.append(str(open_rows[:200]))

    blocks.append("## Raw Execution Logs")
    for i, r in enumerate(scan_results, 1):
        blocks.append(
            f"""### [{i:02d}] {r['tool']}
command: {" ".join(r["command"])}
returncode: {r["returncode"]}

stdout:
{(r["stdout"] or "")[:10000]}

stderr:
{(r["stderr"] or "")[:6000]}
"""
        )
    return "\n\n".join(blocks)
