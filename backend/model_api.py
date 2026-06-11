
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Iterator

import requests


def load_env_files() -> None:
    roots = [Path(__file__).resolve().parent.parent / ".env"]
    for env_path in roots:
        try:
            if not env_path.exists():
                continue
            lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
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


def _normalize_anthropic_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _anthropic_headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": os.getenv("MINIMAX_ANTHROPIC_VERSION", "2023-06-01"),
        "Content-Type": "application/json",
    }


def _to_anthropic_payload(messages: list[dict[str, str]], model: str, temperature: float, stream: bool = False) -> dict[str, Any]:
    system_parts: list[str] = []
    chat_messages: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            if content:
                system_parts.append(content)
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        chat_messages.append({"role": role, "content": [{"type": "text", "text": content}]})
    if not chat_messages:
        chat_messages.append({"role": "user", "content": [{"type": "text", "text": "请用中文回复：模型连通性测试。"}]})
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": int(os.getenv("MINIMAX_MAX_TOKENS", "2048")),
        "messages": chat_messages,
        "temperature": temperature,
        "stream": stream,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    return payload


def _extract_anthropic_text(payload: dict[str, Any]) -> str:
    parts = []
    for item in payload.get("content", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
    return "".join(parts).strip()


def model_config() -> dict[str, Any]:
    qwen_key = os.getenv("META_API_KEY") or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    zhipu_key = os.getenv("ZHIPU_API_KEY", "")
    local_key = os.getenv("LOCAL_API_KEY", "")
    if qwen_key:
        return {
            "provider": "Qwen",
            "api_key": qwen_key,
            "base_url": os.getenv("META_BASE_URL") or os.getenv("QWEN_BASE_URL", ""),
            "model": os.getenv("META_MODEL_NAME") or os.getenv("QWEN_MODEL", "qwen-plus-latest"),
            "api_format": "openai",
        }
    if zhipu_key:
        return {
            "provider": "Zhipu",
            "api_key": zhipu_key,
            "base_url": os.getenv("ZHIPU_BASE_URL", ""),
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


def meta_model_config() -> dict[str, Any]:
    api_key = os.getenv("META_API_KEY") or os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    return {
        "provider": "Qwen",
        "api_key": api_key,
        "base_url": os.getenv("META_BASE_URL") or os.getenv("QWEN_BASE_URL", ""),
        "model": os.getenv("META_MODEL_NAME") or os.getenv("QWEN_MODEL", "qwen-plus-latest"),
    }


def public_model_status() -> dict[str, Any]:
    cfg = model_config()
    return {"provider": cfg["provider"], "model": cfg.get("model") or "", "available": bool(cfg.get("api_key")), "api_format": cfg.get("api_format", "")}


def public_meta_model_status() -> dict[str, Any]:
    cfg = meta_model_config()
    return {"provider": cfg["provider"], "model": cfg.get("model") or "", "available": bool(cfg.get("api_key")), "api_format": "openai"}


def call_chat_stream(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 90) -> Iterator[dict[str, Any]]:
    cfg = model_config()
    if not cfg.get("api_key"):
        yield {"ok": False, "error": "未配置可用的大模型 API；请配置 META_API_KEY、QWEN_API_KEY、DASHSCOPE_API_KEY 或 LOCAL_BASE_URL。"}
        return
    try:
        if cfg.get("api_format") == "anthropic":
            resp = requests.post(
                _normalize_anthropic_url(cfg["base_url"]),
                headers=_anthropic_headers(cfg["api_key"]),
                json=_to_anthropic_payload(messages, cfg["model"], temperature, stream=True),
                timeout=timeout,
                stream=True,
            )
            if resp.status_code >= 400:
                yield {"ok": False, "error": f"{cfg['provider']} API HTTP {resp.status_code}: {resp.text[:300]}"}
                return
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    payload = json.loads(data_str)
                except Exception:
                    continue
                delta = payload.get("delta") or {}
                content = delta.get("text", "")
                if content:
                    yield {"ok": True, "content": content, "provider": cfg["provider"], "model": cfg["model"]}
            return

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
        return {"ok": False, "content": "", "error": "未配置可用的大模型 API；请配置 META_API_KEY、QWEN_API_KEY、DASHSCOPE_API_KEY 或 LOCAL_BASE_URL。"}
    try:
        if cfg.get("api_format") == "anthropic":
            resp = requests.post(
                _normalize_anthropic_url(cfg["base_url"]),
                headers=_anthropic_headers(cfg["api_key"]),
                json=_to_anthropic_payload(messages, cfg["model"], temperature),
                timeout=timeout,
            )
            if resp.status_code >= 400:
                return {"ok": False, "content": "", "error": f"{cfg['provider']} API HTTP {resp.status_code}: {resp.text[:300]}"}
            payload = resp.json()
            content = _extract_anthropic_text(payload)
            return {"ok": True, "content": content, "provider": cfg["provider"], "model": cfg["model"], "raw": payload}

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


def call_meta_chat(messages: list[dict[str, str]], temperature: float = 0.2, timeout: int = 60) -> dict[str, Any]:
    cfg = meta_model_config()
    if not cfg.get("api_key"):
        return {"ok": False, "content": "", "error": "违规检测未配置 Qwen API；请配置 META_API_KEY。"}
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


def _token_probability_stats_from_logprobs(logprobs_payload: Any) -> dict[str, Any]:
    probabilities: list[float] = []
    content_items: list[Any] = []
    if isinstance(logprobs_payload, dict):
        content_items = logprobs_payload.get("content") or []
    elif isinstance(logprobs_payload, list):
        content_items = logprobs_payload
    for item in content_items:
        if not isinstance(item, dict):
            continue
        value = item.get("logprob")
        if value is None:
            continue
        try:
            probabilities.append(math.exp(float(value)))
        except Exception:
            continue
    if not probabilities:
        return {
            "min_token_probability": None,
            "avg_token_probability": None,
            "token_probability_count": 0,
            "token_probability_available": False,
        }
    return {
        "min_token_probability": round(min(probabilities), 6),
        "avg_token_probability": round(sum(probabilities) / len(probabilities), 6),
        "token_probability_count": len(probabilities),
        "token_probability_available": True,
    }


def call_chat_with_logprobs(
    messages: list[dict[str, str]],
    temperature: float = 0.0,
    timeout: int = 90,
    top_logprobs: int = 1,
    seed: int | None = None,
) -> dict[str, Any]:
    cfg = model_config()
    if not cfg.get("api_key"):
        return {"ok": False, "content": "", "error": "未配置可用的大模型 API；请配置 META_API_KEY、QWEN_API_KEY、DASHSCOPE_API_KEY 或 LOCAL_BASE_URL。"}

    if cfg.get("api_format") == "anthropic":
        result = call_chat(messages, temperature=temperature, timeout=timeout)
        result.update(
            {
                "min_token_probability": None,
                "avg_token_probability": None,
                "token_probability_count": 0,
                "token_probability_available": False,
                "logprobs_note": "当前模型接口未返回 token 概率，已继续执行内容匹配判别。",
            }
        )
        return result

    try:
        payload: dict[str, Any] = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "logprobs": True,
            "top_logprobs": top_logprobs,
        }
        if seed is not None:
            payload["seed"] = seed
        resp = requests.post(
            _normalize_chat_url(cfg["base_url"]),
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            fallback = call_chat(messages, temperature=temperature, timeout=timeout)
            fallback.update(
                {
                    "min_token_probability": None,
                    "avg_token_probability": None,
                    "token_probability_count": 0,
                    "token_probability_available": False,
                    "logprobs_note": f"{cfg['provider']} API 未返回可用 token 概率，已继续执行内容匹配判别。",
                }
            )
            return fallback
        raw = resp.json()
        choice = (raw.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content", "")
        stats = _token_probability_stats_from_logprobs(choice.get("logprobs"))
        return {"ok": True, "content": content, "provider": cfg["provider"], "model": cfg["model"], "raw": raw, **stats}
    except Exception as exc:
        fallback = call_chat(messages, temperature=temperature, timeout=timeout)
        fallback.update(
            {
                "min_token_probability": None,
                "avg_token_probability": None,
                "token_probability_count": 0,
                "token_probability_available": False,
                "logprobs_note": f"token 概率调用失败，已继续执行内容匹配判别：{exc}",
            }
        )
        return fallback


def call_meta_chat_with_logprobs(
    messages: list[dict[str, str]],
    temperature: float = 0.0,
    timeout: int = 90,
    top_logprobs: int = 1,
    seed: int | None = None,
) -> dict[str, Any]:
    cfg = meta_model_config()
    if not cfg.get("api_key"):
        return {"ok": False, "content": "", "error": "违规检测未配置 Qwen API；请配置 META_API_KEY。"}
    try:
        payload: dict[str, Any] = {
            "model": cfg["model"],
            "messages": messages,
            "temperature": temperature,
            "logprobs": True,
            "top_logprobs": top_logprobs,
        }
        if seed is not None:
            payload["seed"] = seed
        resp = requests.post(
            _normalize_chat_url(cfg["base_url"]),
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            fallback = call_meta_chat(messages, temperature=temperature, timeout=timeout)
            fallback.update(
                {
                    "min_token_probability": None,
                    "avg_token_probability": None,
                    "token_probability_count": 0,
                    "token_probability_available": False,
                    "logprobs_note": f"{cfg['provider']} API 未返回可用 token 概率，已继续执行内容匹配判别。",
                }
            )
            return fallback
        raw = resp.json()
        choice = (raw.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content", "")
        stats = _token_probability_stats_from_logprobs(choice.get("logprobs"))
        return {"ok": True, "content": content, "provider": cfg["provider"], "model": cfg["model"], "raw": raw, **stats}
    except Exception as exc:
        fallback = call_meta_chat(messages, temperature=temperature, timeout=timeout)
        fallback.update(
            {
                "min_token_probability": None,
                "avg_token_probability": None,
                "token_probability_count": 0,
                "token_probability_available": False,
                "logprobs_note": f"token 概率调用失败，已继续执行内容匹配判别：{exc}",
            }
        )
        return fallback
