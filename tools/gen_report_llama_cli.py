import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def format_alert_block(a: Dict[str, Any]) -> str:
    # LLMに渡す“要点”だけに絞って、トークン節約＆安定化
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

def call_llama_cli(llama_cli: Path, model: Path, prompt: str, ctx: int, n_tokens: int, temp: float) -> str:
    # llama.cpp は基本UTF-8で渡す想定。Windows端末表示が怪しい時でもファイル出力は安定しやすいです。
    cmd = [
    str(llama_cli),
    "-m", str(model),
    "--ctx-size", str(ctx),
    "-n", str(n_tokens),
    "--temp", str(temp),
    "--log-disable",
    "--no-display-prompt",
    "-p", prompt
        ]

    # 出力を確実に取得する
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if proc.returncode != 0:
        raise RuntimeError(f"llama-cli failed: code={proc.returncode}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")
    return proc.stdout

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="zap_high.json (output from extract)")
    ap.add_argument("--template", required=True, help="prompt template txt")
    ap.add_argument("--llama_cli", required=True, help="path to llama-cli.exe")
    ap.add_argument("--model", required=True, help="path to gguf model")
    ap.add_argument("--out", dest="outp", required=True, help="output report.md")
    ap.add_argument("--ctx", type=int, default=2048)
    ap.add_argument("--n", type=int, default=512)
    ap.add_argument("--temp", type=float, default=0.4)
    args = ap.parse_args()

    in_path = Path(args.inp)
    template_path = Path(args.template)
    llama_cli = Path(args.llama_cli)
    model = Path(args.model)
    out_path = Path(args.outp)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(read_text(in_path))
    alerts = data.get("alerts", [])
    template = read_text(template_path)

    sections = []
    sections.append(f"# ZAP診断ドラフト（自動生成）\n\n- 入力: `{in_path}`\n- 抽出条件: min_risk={data.get('min_risk')}\n- 件数: {data.get('count_filtered')}/{data.get('count_total')}\n")

    for i, a in enumerate(alerts, start=1):
        alert_block = format_alert_block(a)

        prompt = template.format(
            alert_name=a.get("alert_name",""),
            risk_level=a.get("risk_level",""),
            confidence=a.get("confidence",""),
            cweid=a.get("cweid",""),
            wascid=a.get("wascid",""),
            alert_block=alert_block
        )

        print(f"[{i}/{len(alerts)}] generating: {a.get('alert_name')} ({a.get('risk_level')})")
        out = call_llama_cli(llama_cli, model, prompt, args.ctx, args.n, args.temp)

        # llama-cli の出力にはログっぽい行が混ざることがあるので、最低限整形
        cleaned = out.strip()

        sections.append("\n---\n\n" + cleaned + "\n")

    out_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"OK: wrote {out_path}")

if __name__ == "__main__":
    main()
