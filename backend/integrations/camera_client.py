from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Callable

import requests


FrameBuilder = Callable[[dict[str, Any]], list[dict[str, Any]]]


class CameraClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("CAMERA_API_URL", "").rstrip("/")
        self.token = os.getenv("CAMERA_API_TOKEN", "")
        self.timeout = int(os.getenv("CAMERA_API_TIMEOUT", "20"))
        self.mock_fallback = os.getenv("CAMERA_API_MOCK_FALLBACK", "1") != "0"

    def get_recent_frames(
        self,
        ticket: dict[str, Any],
        fallback_builder: FrameBuilder,
        window_minutes: int | None = None,
        interval_minutes: int | None = None,
    ) -> list[dict[str, Any]]:
        window = window_minutes or int(os.getenv("CAMERA_DEFAULT_WINDOW_MINUTES", "30"))
        interval = interval_minutes or int(os.getenv("CAMERA_DEFAULT_INTERVAL_MINUTES", "1"))
        if not self.base_url:
            return self._fallback(ticket, fallback_builder, "未配置监控抽帧接口，已使用演示画面兜底。")
        try:
            payload = self._build_payload(ticket, window, interval)
            response = requests.post(
                self.base_url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            frames = self._normalize_response(response.json(), ticket)
            if frames:
                return frames[: max(1, window // interval)]
            raise ValueError("监控抽帧接口未返回图片帧")
        except Exception as exc:
            if not self.mock_fallback:
                raise
            return self._fallback(ticket, fallback_builder, f"监控抽帧接口不可用，已使用演示画面兜底：{exc}")

    def _build_payload(self, ticket: dict[str, Any], window_minutes: int, interval_minutes: int) -> dict[str, Any]:
        fact = ticket.get("ticket_fact") or {}
        task = ticket.get("media_query_task") or {}
        args = task.get("arguments") or {}
        candidates = args.get("candidate_cameras") or []
        camera_ids = [
            item.get("camera_id")
            for item in candidates
            if isinstance(item, dict) and item.get("camera_id")
        ]
        explicit = fact.get("monitor_camera_id") or fact.get("camera_id") or ticket.get("camera_id")
        if explicit and explicit not in camera_ids:
            camera_ids.insert(0, explicit)
        end_time = datetime.now().replace(second=0, microsecond=0)
        start_time = end_time - timedelta(minutes=window_minutes)
        return {
            "plan_id": fact.get("plan_id") or ticket.get("plan_id"),
            "project_name": fact.get("project_name") or ticket.get("project_name"),
            "work_location": fact.get("work_location") or ticket.get("work_location"),
            "camera_ids": camera_ids,
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "interval_seconds": interval_minutes * 60,
            "count": max(1, window_minutes // interval_minutes),
            "ticket_context": fact,
        }

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _normalize_response(self, payload: Any, ticket: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            rows = payload.get("frames") or payload.get("items") or payload.get("data") or []
        else:
            rows = payload
        if not isinstance(rows, list):
            return []
        normalized = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            image_url = row.get("thumbnail_path") or row.get("thumbnail_url") or row.get("image_url") or row.get("file_path") or row.get("url")
            normalized.append(
                {
                    "media_id": row.get("media_id") or row.get("id") or f"camera_frame_{index:02d}",
                    "display_label": row.get("display_label") or f"第{index:02d}帧",
                    "media_type": "现场图片",
                    "camera_id": row.get("camera_id") or row.get("monitor_id") or "",
                    "camera_name": row.get("camera_name") or row.get("monitor_name") or "固定监控",
                    "capture_time": row.get("capture_time") or row.get("timestamp") or "",
                    "file_path": row.get("file_path") or image_url or "",
                    "thumbnail_path": image_url or row.get("file_path") or "",
                    "status": "真实接口",
                    "minute_index": row.get("minute_index") or index,
                    "work_location": row.get("work_location") or ticket.get("work_location"),
                    "source_asset": row.get("source_asset") or "内网监控抽帧接口",
                    "dedupe_key": row.get("dedupe_key") or f"{row.get('camera_id', '')}-{row.get('capture_time', '')}-{index}",
                    "raw_frame": row,
                }
            )
        return normalized

    def _fallback(self, ticket: dict[str, Any], fallback_builder: FrameBuilder, message: str) -> list[dict[str, Any]]:
        frames = fallback_builder(ticket)
        for frame in frames:
            frame["retrieval_status"] = message
            frame.setdefault("status", "演示兜底")
        return frames
