import json
import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

RISK_ORDER = {"Informational": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}

def _risk_to_int(risk: str) -> int:
    if not risk:
        return -1
    r = risk.strip().capitalize()
    # ZAPは "Informational" / "Low" / "Medium" / "High" が多い。環境によっては "Critical" も。
    return RISK_ORDER.get(r, RISK_ORDER.get(risk.strip(), -1))

def _pick(d: Dict[str, Any], *keys: str, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default

def normalize_alert(a: Dict[str, Any]) -> Dict[str, Any]:
    alert_name = _pick(a, "alert", "name", "alertName", default="(no name)")
    risk = _pick(a, "risk", "riskdesc", "riskDescription", default="Unknown")
    confidence = _pick(a, "confidence", "conf", default="")
    cweid = _pick(a, "cweid", "cweId", default="")
    wascid = _pick(a, "wascid", "wascId", default="")
    desc = _pick(a, "desc", "description", default="")
    solution = _pick(a, "solution", default="")
    reference = _pick(a, "reference", "references", default="")
    evidence = _pick(a, "evidence", default="")
    other = _pick(a, "otherinfo", "otherInfo", default="")
    # instance / uri / url
    instances = a.get("instances")
    if isinstance(instances, list) and instances:
        # よくある形式：instancesの中に uri/method/param/evidence がある
        first = instances[0] if isinstance(instances[0], dict) else {}
        uri = _pick(first, "uri", "url", "name", default="")
        method = _pick(first, "method", default="")
        param = _pick(first, "param", "parameter", default="")
    else:
        uri = _pick(a, "uri", "url", default="")
        method = _pick(a, "method", default="")
        param = _pick(a, "param", "parameter", default="")

    return {
        "alert_name": str(alert_name),
        "risk_level": str(risk),
        "confidence": str(confidence),
        "cweid": str(cweid),
        "wascid": str(wascid),
        "uri": str(uri),
        "method": str(method),
        "param": str(param),
        "desc": str(desc),
        "solution": str(solution),
        "reference": str(reference),
        "evidence": str(evidence),
        "otherinfo": str(other),
        "raw": a,
    }

def load_zap_alerts(json_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))

    alerts: List[Dict[str, Any]] = []

    # 形1: {"site":[{"alerts":[...]}]}
    if isinstance(data, dict) and "site" in data and isinstance(data["site"], list):
        for site in data["site"]:
            if isinstance(site, dict) and isinstance(site.get("alerts"), list):
                for a in site["alerts"]:
                    if isinstance(a, dict):
                        alerts.append(a)

    # 形2: {"alerts":[...]}
    if isinstance(data, dict) and isinstance(data.get("alerts"), list):
        for a in data["alerts"]:
            if isinstance(a, dict):
                alerts.append(a)

    # 形3: すでに配列だけのJSON
    if isinstance(data, list):
        for a in data:
            if isinstance(a, dict):
                alerts.append(a)

    return alerts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="ZAP alerts json path")
    ap.add_argument("--min_risk", default="High", help="High or Medium ...")
    ap.add_argument("--out", dest="outp", required=True, help="Output normalized json")
    args = ap.parse_args()

    in_path = Path(args.inp)
    out_path = Path(args.outp)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw_alerts = load_zap_alerts(in_path)
    norm = [normalize_alert(a) for a in raw_alerts]

    min_int = _risk_to_int(args.min_risk)
    filtered = [x for x in norm if _risk_to_int(x["risk_level"]) >= min_int]

    # ざっくり見やすい順にソート（risk desc → alert名）
    filtered.sort(key=lambda x: (-_risk_to_int(x["risk_level"]), x["alert_name"]))

    out_obj = {
        "source": str(in_path),
        "count_total": len(norm),
        "count_filtered": len(filtered),
        "min_risk": args.min_risk,
        "alerts": filtered,
    }
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: total={len(norm)} filtered={len(filtered)} -> {out_path}")

if __name__ == "__main__":
    main()
