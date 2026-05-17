"""DashScope model discovery utility. Uses DASHSCOPE_API_KEY env var."""
import os
import sys

os.environ["NO_PROXY"] = "coding.dashscope.aliyuncs.com"
os.environ["no_proxy"] = "coding.dashscope.aliyuncs.com"

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
if not API_KEY:
    print("Error: DASHSCOPE_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

import httpx

BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://coding.dashscope.aliyuncs.com/v1")
headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def try_model(model: str) -> dict:
    """Try a single model. Returns {ok, text}."""
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json={
            "model": model,
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 5,
        }, timeout=30)
        if r.status_code == 200:
            return {"ok": True, "text": r.json()["choices"][0]["message"]["content"]}
        err = r.json().get("error", {}).get("message", "")[:80]
        return {"ok": False, "text": f"{r.status_code}: {err}"}
    except Exception as e:
        return {"ok": False, "text": str(e)[:80]}


def try_models(models: list[str]) -> list[tuple[str, dict]]:
    """Try multiple models. Returns list of (model_name, result)."""
    return [(m, try_model(m)) for m in models]


if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else ["qwen3.6-plus"]
    for model, result in try_models(models):
        icon = "OK" if result["ok"] else "FAIL"
        print(f"  [{icon}] {model}: {result['text']}")
