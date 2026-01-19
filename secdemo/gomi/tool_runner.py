# secdemo/tool_runner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List
import subprocess
import shlex

@dataclass
class ToolResult:
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool

def run_command(command: str, timeout_sec: int = 120) -> ToolResult:
    args = shlex.split(command)
    try:
        cp = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
        return ToolResult(args, cp.returncode, cp.stdout, cp.stderr, timed_out=False)
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = e.stderr or ""
        return ToolResult(args, returncode=-1, stdout=out, stderr=err, timed_out=True)
