#!/usr/bin/env python3
"""
scripts/test_endpoint.py
========================
Smoke-tests your deployed Modal endpoint.

Usage:
  python scripts/test_endpoint.py --url https://YOUR-WORKSPACE--gemma-openai-server.modal.run
"""
import argparse
import json
import urllib.request
import urllib.error
import sys
import time


def test_health(base_url: str) -> bool:
    url = f"{base_url}/health"
    print(f"🔍  GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"    ✅  Status: {data}")
            return True
    except Exception as e:
        print(f"    ❌  {e}")
        return False


def test_models(base_url: str) -> bool:
    url = f"{base_url}/v1/models"
    print(f"🔍  GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
            models = [m["id"] for m in data.get("data", [])]
            print(f"    ✅  Models: {models}")
            return True
    except Exception as e:
        print(f"    ❌  {e}")
        return False


def test_chat(base_url: str, model_id: str) -> bool:
    url = f"{base_url}/v1/chat/completions"
    payload = json.dumps({
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "Write a C# record type for a Person with Name and Age."},
        ],
        "max_tokens": 256,
        "temperature": 0.3,
    }).encode()

    print(f"🔍  POST {url}")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - t0
            content = data["choices"][0]["message"]["content"]
            usage   = data.get("usage", {})
            print(f"    ✅  Response in {elapsed:.1f}s")
            print(f"    📊  Tokens: {usage}")
            print(f"    💬  Output:\n")
            print("─" * 60)
            print(content)
            print("─" * 60)
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"    ❌  HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"    ❌  {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Modal Gemma endpoint")
    parser.add_argument("--url",   required=True, help="Base URL of your Modal deployment")
    parser.add_argument("--model", default="google/gemma-3-4b-it", help="Model ID")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    print(f"\n🚀  Testing Modal endpoint: {base}\n")

    results = [
        test_health(base),
        test_models(base),
        test_chat(base, args.model),
    ]

    print()
    passed = sum(results)
    total  = len(results)
    if passed == total:
        print(f"✅  All {total} tests passed!")
        print(f"\n📋  Add to VS Code Copilot BYOK:")
        print(f"    Base URL: {base}/v1")
        print(f"    Model:    {args.model}")
    else:
        print(f"⚠️   {passed}/{total} tests passed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
