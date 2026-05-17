"""Call DashScope coding model and return the response.

Usage:
    python ask_model.py "Write a Python function to reverse a string"
    python ask_model.py --system "You are a Python expert" "Explain list comprehensions"

Reads from stdin if no args provided.

Environment variables:
    DASHSCOPE_API_KEY: API key (sk-sp-...)
    DASHSCOPE_BASE_URL: Base URL (default: https://coding.dashscope.aliyuncs.com/v1)
    DASHSCOPE_MODEL: Model name (default: qwen3.6-plus)
"""
import json
import os
import sys

# Read from environment variables
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://coding.dashscope.aliyuncs.com/v1")
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
MODEL = os.getenv("DASHSCOPE_MODEL", "qwen3.6-plus")

if not API_KEY:
    print("Error: DASHSCOPE_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

# Bypass proxy for DashScope - must be set BEFORE importing httpx/openai
os.environ["NO_PROXY"] = "coding.dashscope.aliyuncs.com"
os.environ["no_proxy"] = os.environ["NO_PROXY"]

from openai import OpenAI

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    # Explicitly disable proxy to bypass system proxy settings
    http_client=None,
)


def ask_model(prompt: str, system: str = "You are a helpful coding assistant. Reply concisely.") -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2048,
        temperature=0.2,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ask DashScope coding model")
    parser.add_argument("prompt", nargs="?", help="Prompt to send")
    parser.add_argument("--system", default="You are a helpful coding assistant. Reply concisely.", help="System prompt")
    args = parser.parse_args()

    prompt = args.prompt
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            print("Error: provide a prompt as argument or via stdin", file=sys.stderr)
            sys.exit(1)

    try:
        result = ask_model(prompt, system=args.system)
        print(result)
    except Exception as e:
        print(f"Model error: {e}", file=sys.stderr)
        sys.exit(1)
