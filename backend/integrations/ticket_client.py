from __future__ import annotations

import os
from typing import Any

import requests


class TicketClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("TICKET_API_URL", "").rstrip("/")
        self.token = os.getenv("TICKET_API_TOKEN", "")
        self.timeout = int(os.getenv("TICKET_API_TIMEOUT", "30"))

    def configured(self) -> bool:
        return bool(self.base_url)

    def fetch_ticket(self, plan_id: str) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("未配置作业票接口地址")
        response = requests.get(
            f"{self.base_url}/{plan_id}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("作业票接口返回格式不是 JSON 对象")
        return payload

    def submit_parse_result(self, record: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("未配置作业票接口地址")
        response = requests.post(
            self.base_url,
            headers=self._headers(),
            json=record,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"success": True, "raw": payload}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
