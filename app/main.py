from llama_cpp import Llama
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
args = parser.parse_args()

llm = Llama(
    model_path=args.model,
    n_ctx=2048,
)

print("=== LLM 起動完了 ===")
print("Ctrl+C で終了\n")

while True:
    prompt = input("You> ")
    if not prompt:
        continue

    res = llm(
        prompt,
        max_tokens=256,
        stop=["You>"]
    )

    print("LLM>", res["choices"][0]["text"])
