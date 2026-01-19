from typing import Any, Dict, List, Optional, Tuple
import requests



def zap_json_get(base: str, path: str, apikey: str = "", params: Optional[Dict[str, Any]] = None, timeout: int = 20):
    params = dict(params or {})
    if apikey:
        params["apikey"] = apikey
    url = base.rstrip("/") + path
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def connect(base: str, apikey: str) -> Tuple[bool, str, str, str]:
    try:
        v = zap_json_get(base, "/JSON/core/view/version/", apikey, timeout=8)
        version = v.get("version", "")
        mode = ""
        try:
            m = zap_json_get(base, "/JSON/core/view/mode/", apikey, timeout=8)
            mode = m.get("mode", "")
        except Exception:
            mode = ""
        return True, version, mode, ""
    except Exception as e:
        return False, "", "", str(e)

def list_sites(base: str, apikey: str) -> List[str]:
    data = zap_json_get(base, "/JSON/core/view/sites/", apikey, timeout=20)
    sites = data.get("sites", [])
    if isinstance(sites, list):
        return [str(s) for s in sites]
    return []

def history_messages(base: str, apikey: str, start: int = 0, count: int = 100, url_regex: str = "") -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"start": start, "count": count}
    if url_regex:
        params["urlRegex"] = url_regex
    data = zap_json_get(base, "/JSON/core/view/messages/", apikey, params=params, timeout=30)
    msgs = data.get("messages", [])
    if not isinstance(msgs, list):
        return []
    return [m for m in msgs if isinstance(m, dict)]

def message_by_id(base: str, apikey: str, msgid: str) -> Optional[Dict[str, Any]]:
    try:
        data = zap_json_get(base, "/JSON/core/view/message/", apikey, params={"id": msgid}, timeout=30)
        if "message" in data and isinstance(data["message"], dict):
            return data["message"]
        if any(k in data for k in ["requestHeader", "responseHeader", "requestBody", "responseBody"]):
            return data
    except Exception:
        pass

    try:
        data = zap_json_get(base, "/JSON/core/view/messagesById/", apikey, params={"ids": msgid}, timeout=30)
        msgs = data.get("messages", [])
        if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
            return msgs[0]
    except Exception:
        pass

    return None

def send_request(base: str, apikey: str, raw_request: str, follow_redirects: bool = True) -> Dict[str, Any]:
    params = {"request": raw_request, "followRedirects": str(follow_redirects).lower()}
    return zap_json_get(base, "/JSON/core/action/sendRequest/", apikey, params=params, timeout=90)

def fetch_alerts(base: str, apikey: str, baseurl: str = "") -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if baseurl:
        params["baseurl"] = baseurl
    return zap_json_get(base, "/JSON/core/view/alerts/", apikey, params=params, timeout=60)

def spider_scan(base: str, apikey: str, url: str, max_children: int = 0, recurse: bool = True, subtree_only: bool = False) -> str:
    params = {
        "url": url,
        "maxChildren": str(max_children),
        "recurse": str(recurse).lower(),
        "subtreeOnly": str(subtree_only).lower(),
    }
    data = zap_json_get(base, "/JSON/spider/action/scan/", apikey, params=params, timeout=60)
    return str(data.get("scan", ""))

def spider_status(base: str, apikey: str, scan_id: str) -> int:
    data = zap_json_get(base, "/JSON/spider/view/status/", apikey, params={"scanId": scan_id}, timeout=20)
    try:
        return int(data.get("status", 0))
    except Exception:
        return 0

def ascan_scan(base: str, apikey: str, url: str, recurse: bool = True, in_scope_only: bool = False) -> str:
    params = {
        "url": url,
        "recurse": str(recurse).lower(),
        "inScopeOnly": str(in_scope_only).lower(),
    }
    data = zap_json_get(base, "/JSON/ascan/action/scan/", apikey, params=params, timeout=60)
    return str(data.get("scan", ""))

def ascan_status(base: str, apikey: str, scan_id: str) -> int:
    data = zap_json_get(base, "/JSON/ascan/view/status/", apikey, params={"scanId": scan_id}, timeout=20)
    try:
        return int(data.get("status", 0))
    except Exception:
        return 0

async def messages(self, baseurl: str | None = None, start: int = 0, count: int = 200):
    params = {"start": start, "count": count}
    if baseurl:
        params["baseurl"] = baseurl
    return await self._get_json("/JSON/core/view/messages/", params=params)
