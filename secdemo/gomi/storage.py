# secdemo/storage.py
from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional



def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path

def _path_for_tag(store_dir: str, tag: str) -> str:
    ensure_dir(store_dir)
    safe = "".join(c for c in tag if c.isalnum() or c in ("-", "_")).strip() or "default"
    return os.path.join(store_dir, f"history_{safe}.jsonl")

def append_item(store_dir: str, tag: str, item: Dict[str, Any]) -> None:
    p = _path_for_tag(store_dir, tag)
    item = dict(item)
    item.setdefault("saved_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

def load_items(store_dir: str, tag: str, limit: int = 200) -> List[Dict[str, Any]]:
    p = _path_for_tag(store_dir, tag)
    if not os.path.exists(p):
        return []
    items: List[Dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    # latest first
    items.reverse()
    return items[:limit]

def search_items(items: List[Dict[str, Any]], q: str) -> List[Dict[str, Any]]:
    q = (q or "").strip().lower()
    if not q:
        return items
    out = []
    for it in items:
        blob = " ".join([
            str(it.get("title","")),
            str(it.get("url","")),
            str(it.get("method","")),
            str(it.get("note","")),
            str(it.get("raw_request","")),
            str(it.get("raw_response","")),
            str(it.get("tags","")),
        ]).lower()
        if q in blob:
            out.append(it)
    return out
