"""Cliente da API administrativa local do VOXEL Router."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class LocalApiError(RuntimeError):
    """Falha de comunicação ou autorização na API local."""


class LocalApiClient:
    """Acessa a API do Router exclusivamente pelo loopback local."""

    def __init__(self, token_path: Path, host: str = "127.0.0.1", port: int = 17841) -> None:
        self.token_path = token_path
        self.base_url = f"http://{host}:{port}"

    def health(self) -> dict[str, Any]:
        return self._request("/health", protected=False)

    def status(self) -> dict[str, Any]:
        return self._request("/status")

    def worklist(self) -> list[dict[str, Any]]:
        return self._request("/worklist")

    def modalities(self) -> list[dict[str, Any]]:
        return self._request("/modalities")

    def queue(self) -> list[dict[str, Any]]:
        return self._request("/queue")

    def logs(self) -> list[dict[str, Any]]:
        return self._request("/logs")

    def retry_queue_item(self, queue_id: int) -> dict[str, Any]:
        return self._request(f"/queue/{queue_id}/retry", method="POST", payload={})

    def _request(
        self,
        path: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        protected: bool = True,
    ) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if protected:
            headers["X-VOXEL-Router-Token"] = self._token()
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
            raise LocalApiError("Não foi possível consultar o serviço local do Router.") from error

    def _token(self) -> str:
        try:
            token = self.token_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise LocalApiError("Não foi possível ler o token administrativo local.") from error
        if not token:
            raise LocalApiError("O token administrativo local está vazio.")
        return token
