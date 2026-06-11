from __future__ import annotations

import os
from typing import Any, Callable

import requests


VisionFallback = Callable[[list[dict[str, Any]], dict[str, Any]], dict[str, Any]]


class VisionClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("VISION_API_URL", "").rstrip("/")
        self.token = os.getenv("VISION_API_TOKEN", "")
        self.timeout = int(os.getenv("VISION_API_TIMEOUT", "90"))
        self.mock_fallback = os.getenv("VISION_API_MOCK_FALLBACK", "1") != "0"

    def analyze_site_evidence(
        self,
        frames: list[dict[str, Any]],
        ticket: dict[str, Any],
        fallback_analyzer: VisionFallback,
    ) -> dict[str, Any]:
        if not self.base_url:
            return self._fallback(frames, ticket, fallback_analyzer, "未配置视觉理解接口，已使用演示视觉证据包兜底。")
        try:
            response = requests.post(
                self.base_url,
                headers=self._headers(),
                json=self._payload(frames, ticket),
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("视觉理解接口返回格式不是 JSON 对象")
            return self._normalize_result(result, frames)
        except Exception as exc:
            if not self.mock_fallback:
                raise
            return self._fallback(frames, ticket, fallback_analyzer, f"视觉理解接口不可用，已使用演示视觉证据包兜底：{exc}")

    def _payload(self, frames: list[dict[str, Any]], ticket: dict[str, Any]) -> dict[str, Any]:
        fact = ticket.get("ticket_fact") or {}
        return {
            "task": "现场事实证据提取",
            "instruction": "只输出现场事实证据包，不直接输出最终违规裁决。",
            "ticket_context": fact,
            "frames": [
                {
                    "media_id": frame.get("media_id"),
                    "camera_id": frame.get("camera_id"),
                    "camera_name": frame.get("camera_name"),
                    "capture_time": frame.get("capture_time"),
                    "image_url": frame.get("file_path") or frame.get("thumbnail_path"),
                }
                for frame in frames
            ],
        }

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _normalize_result(self, result: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, Any]:
        result.setdefault("model_name", "内网视觉理解接口")
        result.setdefault("frame_count", len(frames))
        result.setdefault("frames", result.get("evidence_frames") or [])
        result.setdefault("aggregates", {})
        result["output_boundary"] = "现场事实证据包，不直接作最终违规裁决"
        result["final_decision_allowed"] = False
        result["source"] = "real_vision_api"
        return result

    def _fallback(
        self,
        frames: list[dict[str, Any]],
        ticket: dict[str, Any],
        fallback_analyzer: VisionFallback,
        message: str,
    ) -> dict[str, Any]:
        result = fallback_analyzer(frames, ticket)
        result["source"] = "mock_fallback"
        result["fallback_reason"] = message
        result["output_boundary"] = "现场事实证据包，不直接作最终违规裁决"
        result["final_decision_allowed"] = False
        return result
