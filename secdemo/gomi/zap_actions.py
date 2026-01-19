# secdemo/zap_actions.py
from __future__ import annotations
from typing import Any, Dict, Optional
import httpx

class ZapActions:
    def __init__(self, zap_base: str, apikey: str = "", timeout: float = 30.0):
        self.zap_base = (zap_base or "").rstrip("/")
        self.apikey = apikey or ""
        self.timeout = timeout

    def _params(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        p = dict(extra or {})
        if self.apikey:
            p["apikey"] = self.apikey
        return p

    def _get_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.zap_base}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    def spider_start(self, url: str, max_children: int = 0, recurse: bool = True) -> str:
        params = self._params({"url": url, "maxChildren": max_children, "recurse": "true" if recurse else "false"})
        data = self._get_json("/JSON/spider/action/scan/", params)
        return str(data.get("scan", ""))

    def spider_status(self, scan_id: str) -> int:
        params = self._params({"scanId": scan_id})
        data = self._get_json("/JSON/spider/view/status/", params)
        return int(data.get("status", 0))

    def ascan_start(self, url: str, recurse: bool = True, in_scope_only: bool = False) -> str:
        params = self._params({"url": url, "recurse": "true" if recurse else "false", "inScopeOnly": "true" if in_scope_only else "false"})
        data = self._get_json("/JSON/ascan/action/scan/", params)
        return str(data.get("scan", ""))

    def ascan_status(self, scan_id: str) -> int:
        params = self._params({"scanId": scan_id})
        data = self._get_json("/JSON/ascan/view/status/", params)
        return int(data.get("status", 0))
