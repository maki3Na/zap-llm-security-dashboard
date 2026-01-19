import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
import requests
import re


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def format_alert_block(a: Dict[str, Any]) -> str:
    """
    LLMに渡す“要点”だけに絞って、トークン節約＆安定化
    """
    parts = []
    parts.append(f"alert_name: {a.get('alert_name','')}")
    parts.append(f"risk_level: {a.get('risk_level','')}")
    parts.append(f"confidence: {a.get('confidence','')}")
    parts.append(f"cweid: {a.get('cweid','')}")
    parts.append(f"wascid: {a.get('wascid','')}")
    parts.append(f"uri: {a.get('uri','')}")
    parts.append(f"method: {a.get('method','')}")
    parts.append(f"param: {a.get('param','')}")

    desc = (a.get("desc") or "").strip()
    if desc:
        parts.append("desc:\n" + desc)

    sol = (a.get("solution") or "").strip()
    if sol:
        parts.append("solution:\n" + sol)

    ev = (a.get("evidence") or "").strip()
    if ev:
        parts.append("evidence:\n" + ev)

    other = (a.get("otherinfo") or "").strip()
    if other:
        parts.append("otherinfo:\n" + other)

    ref = (a.get("reference") or "").strip()
    if ref:
        parts.append("reference:\n" + ref)

    return "\n".join(parts)


def sanitize_md(md: str) -> str:
    """
    出力の“型”を強制する後処理。
    - 中国語見出しを日本語に寄せる
    - 「再現方法」は本文を必ず空欄化（次の見出しまで削除）
    - 文字化けっぽい単独行の除去
    """
    # 1) 中国語見出しを日本語へ寄せる（最低限）
    md = md.replace("#### 影响", "#### 影響").replace("### 影响", "### 影響")

    # 2) 「再現方法」配下を空欄にする
    # - 見出しレベルが ### / #### どちらでも対応
    # - 次の見出し（### or ####）または文末までを削る
    pattern = r"(^#{3,4}\s*再現方法\s*\n)(.*?)(?=\n#{3,4}\s|\Z)"
    md = re.sub(pattern, r"\1- \n", md, flags=re.S | re.M)

    # 3) 文字化けっぽい単独行を除去（よくある混入）
    md = md.replace("\n- �\n", "\n")

    # 4) 余計な連続空行を軽く整形（任意）
    md = re.sub(r"\n{4,}", "\n\n\n", md)

    return md


def call_llama_server_chat(
    base_url: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_sec: int,
    retry_503: int = 3,
) -> str:
    """
    llama-server (OpenAI互換) の /v1/chat/completions を叩く
    - 503 対策で軽いリトライ
    - 失敗時はレスポンス本文も出して原因が分かるようにする
    """
    import time

    url = base_url.rstrip("/") + "/v1/chat/completions"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(retry_503 + 1):
        try:
            r = requests.post(url, json=payload, timeout=timeout_sec)

            # 503は混雑やスロット都合で一時的に返ることがあるのでリトライ
            if r.status_code == 503 and attempt < retry_503:
                time.sleep(1.0 + attempt)
                continue

            if not r.ok:
                raise RuntimeError(
                    f"HTTP {r.status_code} {r.reason}\n"
                    f"URL: {url}\n"
                    f"Response text:\n{r.text}\n"
                )

            data = r.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            last_error = e
            if attempt < retry_503:
                time.sleep(1.0 + attempt)
                continue
            break

    raise RuntimeError(
        f"Failed to call llama-server after retries. Last error: {last_error}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="inp",
        required=True,
        help="zap_mediumplus.json (output from extract)",
    )
    ap.add_argument("--template", required=True, help="prompt template txt")
    ap.add_argument("--out", dest="outp", required=True, help="output report.md")

    # llama-server settings
    ap.add_argument(
        "--base_url", default="http://127.0.0.1:8088", help="llama-server base url"
    )
    ap.add_argument("--model_name", default="qwen", help="model name string for API")
    ap.add_argument(
        "--system",
        default="日本語のみで回答してください。英語・中国語など他言語は禁止。出力はMarkdown。再現方法は見出しのみで本文は空欄にしてください。",
        help="system prompt",
    )

    # generation settings
    ap.add_argument("--max_tokens", type=int, default=400, help="max_tokens per alert")
    ap.add_argument("--temp", type=float, default=0.3)
    ap.add_argument("--timeout", type=int, default=180, help="request timeout seconds")

    args = ap.parse_args()

    in_path = Path(args.inp)
    template_path = Path(args.template)
    out_path = Path(args.outp)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(read_text(in_path))
    alerts: List[Dict[str, Any]] = data.get("alerts", [])
    template = read_text(template_path)

    sections: List[str] = []
    sections.append(
        "# ZAP診断ドラフト（自動生成）\n\n"
        f"- 入力: `{in_path}`\n"
        f"- 抽出条件: min_risk={data.get('min_risk')}\n"
        f"- 件数: {data.get('count_filtered')}/{data.get('count_total')}\n"
        f"- LLM: llama-server @ {args.base_url}\n"
    )

    for i, a in enumerate(alerts, start=1):
        alert_block = format_alert_block(a)

        # テンプレに {alert_name} {risk_level} {confidence} {cweid} {wascid} {alert_block} があればそのまま動く
        user_prompt = template.format(
    alert_name=a.get("alert_name", ""),
    risk_level=a.get("risk_level", ""),
    confidence=a.get("confidence", ""),
    cweid=a.get("cweid", ""),
    wascid=a.get("wascid", ""),
    uri=a.get("uri", "不明"),
    method=a.get("method", "不明"),
    param=a.get("param", "不明"),
    alert_block=alert_block,
)


        print(
            f"[{i}/{len(alerts)}] generating via HTTP: {a.get('alert_name')} ({a.get('risk_level')})"
        )

        content = call_llama_server_chat(
            base_url=args.base_url,
            model_name=args.model_name,
            system_prompt=args.system,
            user_prompt=user_prompt,
            temperature=args.temp,
            max_tokens=args.max_tokens,
            timeout_sec=args.timeout,
        )

        # ★後処理で型を強制
        content = sanitize_md(content)

        sections.append("\n---\n\n" + content.strip() + "\n")

    out_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"OK: wrote {out_path}")


if __name__ == "__main__":
    main()
