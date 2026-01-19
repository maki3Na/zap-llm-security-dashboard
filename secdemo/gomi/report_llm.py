# secdemo/report_llm.py
from __future__ import annotations
from typing import Any, Dict
import json
from secdemo.ai_ollama import OllamaChatClient, DEFAULT_SYSTEM

DEFAULT_REPORT_SYSTEM = DEFAULT_SYSTEM + """
あなたはWeb脆弱性診断の報告書作成支援AIです。
入力JSON（alerts/history）を根拠に、日本語のMarkdownで報告書を作ってください。
推測は避け、根拠がある内容のみを書いてください。
"""

def generate_markdown_report(
    ollama_base: str,
    model: str,
    template_text: str,
    report_input: Dict[str, Any],
    temperature: float = 0.2,
) -> str:
    client = OllamaChatClient(base_url=ollama_base, timeout=180)

    user_prompt = (
        "以下のテンプレートに従って、入力JSONを基にMarkdownの診断報告書を作成してください。\n\n"
        "=== TEMPLATE ===\n"
        f"{template_text}\n"
        "=== INPUT_JSON ===\n"
        f"{json.dumps(report_input, ensure_ascii=False, indent=2)}\n"
    )

    return client.chat(
        model=model,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=temperature,
        system=DEFAULT_REPORT_SYSTEM,
    )
