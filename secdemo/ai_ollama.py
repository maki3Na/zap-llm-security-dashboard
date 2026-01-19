# secdemo/ai_ollama.py
from __future__ import annotations

from typing import List, Dict, Optional
import httpx

DEFAULT_SYSTEM = (
    "You are a helpful security assistant. "
    "Do not provide step-by-step exploitation or attack instructions. "
    "Focus on explanation, risk assessment, and defensive guidance."
)


class OllamaChatClient:
    def __init__(self, base_url: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -------------------------
    # Utils
    # -------------------------
    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        r = httpx.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def list_models(self) -> List[str]:
        for path in ("/api/tags", "/v1/models"):
            try:
                url = f"{self.base_url}{path}"
                r = httpx.get(url, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                if "models" in data:
                    return [m["name"] for m in data["models"]]
                if "data" in data:
                    return [m["id"] for m in data["data"]]
            except Exception:
                continue
        return []

    # -------------------------
    # Chat (auto fallback)
    # -------------------------
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        system: Optional[str] = None,
    ) -> str:
        # messages → prompt
        parts = []
        if system:
            parts.append(system)
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"{role.upper()}: {content}")
        prompt = "\n\n".join(parts)

        # ① /api/generate
        try:
            data = self._post(
                "/api/generate",
                {
                    "model": model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                },
            )
            return data.get("response", "")
        except Exception:
            pass

        # ② /api/chat
        try:
            data = self._post(
                "/api/chat",
                {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                },
            )
            return data.get("message", {}).get("content", "")
        except Exception:
            pass

        # ③ OpenAI互換 /v1/completions
        try:
            data = self._post(
                "/v1/completions",
                {
                    "model": model,
                    "prompt": prompt,
                    "temperature": temperature,
                },
            )
            return data["choices"][0]["text"]
        except Exception as e:
            raise RuntimeError(
                "Ollama API endpoint not found. "
                "Ensure 'ollama serve' is running and API is enabled."
            ) from e
