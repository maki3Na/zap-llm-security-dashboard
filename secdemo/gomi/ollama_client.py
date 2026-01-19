import json
import requests


def ollama_status(fallback_model: str = "llama3.1"):
    """
    Ollama の稼働確認 + 利用可能モデル一覧を返す
    Returns:
      (ok: bool, models: list[str], err: str)
    """
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        r.raise_for_status()
        data = r.json()

        models = []
        for m in data.get("models", []):
            name = m.get("name")
            if name:
                models.append(name)

        if not models:
            models = [fallback_model]
        return True, models, ""
    except Exception as e:
        return False, [fallback_model], str(e)


def call_ollama_nonstream(model: str, system: str, user: str, temperature: float = 0.2, timeout: int = 120):
    """
    Ollama /api/chat を非ストリーミングで呼ぶ
    """
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": float(temperature)},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    r = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    # 返り値の形式を吸収
    if isinstance(data, dict):
        msg = data.get("message") or {}
        if isinstance(msg, dict) and "content" in msg:
            return msg["content"]
        # 念のため
        if "response" in data:
            return data["response"]

    return json.dumps(data, ensure_ascii=False)
