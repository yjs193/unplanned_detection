
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

import requests


def load_env_files() -> None:
    roots = [Path(__file__).resolve().parent.parent / ".env"]
    for env_path in roots:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


load_env_files()


def _normalize_chat_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def model_config() -> dict[str, Any]:
    qwen_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    zhipu_key = os.getenv("ZHIPU_API_KEY", "")
    local_key = os.getenv("LOCAL_API_KEY", "")
    if qwen_key:
        return {
            "provider": "Qwen",
            "api_key": qwen_key,
            "base_url": os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
        }
    if zhipu_key:
        return {
            "provider": "Zhipu",
            "api_key": zhipu_key,
            "base_url": os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            "model": os.getenv("ZHIPU_MODEL", "glm-4-plus"),
        }
    if local_key or os.getenv("LOCAL_BASE_URL"):
        return {
            "provider": "Local",
            "api_key": local_key or "EMPTY",
            "base_url": os.getenv("LOCAL_BASE_URL", ""),
            "model": os.getenv("LOCAL_MODEL", "local-model"),
        }
    return {"provider": "未配置", "api_key": "", "base_url": "", "model": ""}


def public_model_status() -> dict[str, Any]:
    cfg = model_config()
    return {"provider": cfg["provider"], "model": cfg.get("model") or "", "available": bool(cfg.get("api_key"))}


def call_chat_stream(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 90) -> Iterator[dict[str, Any]]:
    cfg = model_config()
    if not cfg.get("api_key"):
        yield {"ok": False, "error": "未配置可用的大模型 API；请配置 QWEN_API_KEY 或 ZHIPU_API_KEY。"}
        return
    try:
        resp = requests.post(
            _normalize_chat_url(cfg["base_url"]),
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "messages": messages, "temperature": temperature, "stream": True},
            timeout=timeout,
            stream=True,
        )
        if resp.status_code >= 400:
            yield {"ok": False, "error": f"{cfg['provider']} API HTTP {resp.status_code}: {resp.text[:300]}"}
            return
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                payload = json.loads(data_str)
            except Exception:
                continue
            delta = payload.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield {"ok": True, "content": content, "provider": cfg["provider"], "model": cfg["model"]}
    except Exception as exc:
        yield {"ok": False, "error": f"{cfg['provider']} API 调用失败：{exc}"}


def call_chat(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 60) -> dict[str, Any]:
    cfg = model_config()
    if not cfg.get("api_key"):
        return {"ok": False, "content": "", "error": "未配置可用的大模型 API；请配置 QWEN_API_KEY 或 ZHIPU_API_KEY。"}
    try:
        resp = requests.post(
            _normalize_chat_url(cfg["base_url"]),
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "messages": messages, "temperature": temperature},
            timeout=timeout,
        )
        if resp.status_code >= 400:
            return {"ok": False, "content": "", "error": f"{cfg['provider']} API HTTP {resp.status_code}: {resp.text[:300]}"}
        payload = resp.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "content": content, "provider": cfg["provider"], "model": cfg["model"], "raw": payload}
    except Exception as exc:
        return {"ok": False, "content": "", "error": f"{cfg['provider']} API 调用失败：{exc}"}
