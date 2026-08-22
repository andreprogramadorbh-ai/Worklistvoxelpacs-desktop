from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CloudApiConfig:
    base_url: str
    device_id: str
    bearer_token: str
    timeout_seconds: int = 20


class CloudRouterClient:
    """Cliente HTTP mínimo e explícito para a futura API Router v1 do ERP VOXEL."""

    def __init__(self, config: CloudApiConfig) -> None:
        self.config = config

    def get_config(self) -> dict[str, Any]:
        return self._request("GET", "/api/router/v1/config")

    def sync_worklist(self, cursor: str = "") -> dict[str, Any]:
        suffix = f"?cursor={urllib.parse.quote(cursor)}" if cursor else ""
        return self._request("GET", f"/api/router/v1/worklist/sync{suffix}")

    def publish_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = json.dumps(events, sort_keys=True, separators=(",", ":")).encode("utf-8")
        event_hash = hashlib.sha256(normalized).hexdigest()
        return self._request("POST", "/api/router/v1/events", {"events": events, "batch_hash": event_hash})

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.config.bearer_token}",
                "X-VOXEL-ROUTER-DEVICE": self.config.device_id,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Cloud Router HTTP {response.status}")
                parsed = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as error:
            raise ConnectionError("Cloud Router indisponível") from error
        if not parsed.get("success", False):
            raise RuntimeError(parsed.get("message", "Cloud Router recusou a solicitação"))
        return parsed.get("data", {})
