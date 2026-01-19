# secdemo/zap_live_client.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import httpx

class ZapLiveClient:
    def __init__(self, zap_base: str, apikey: str = "", timeout: float = 15.0):
        self.zap_base = (zap_base or "").rstrip("/")
        self.apikey = apikey or ""
        self.timeout = timeout

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.zap_base:
            raise ValueError("ZAP Base URL is empty")

        params = params or {}
        if self.apikey:
            params["apikey"] = self.apikey

        url = f"{self.zap_base}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    def version(self) -> str:
        data = self._get_json("/JSON/core/view/version/")
        return data.get("version", "")

    def sites(self) -> List[str]:
        data = self._get_json("/JSON/core/view/sites/")
        return data.get("sites", []) or []

    def messages(self, baseurl: Optional[str] = None, start: int = 0, count: int = 200) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"start": start, "count": count}
        if baseurl:
            params["baseurl"] = baseurl
        data = self._get_json("/JSON/core/view/messages/", params=params)
        return data.get("messages", []) or []

    def alerts(self, baseurl: Optional[str] = None, start: int = 0, count: int = 500) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"start": start, "count": count}
        if baseurl:
            params["baseurl"] = baseurl
        data = self._get_json("/JSON/core/view/alerts/", params=params)
        return data.get("alerts", []) or []
