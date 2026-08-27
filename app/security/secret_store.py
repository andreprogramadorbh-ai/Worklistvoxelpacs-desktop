"""Armazenamento de segredos locais protegido por DPAPI no Windows."""
from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping
from pathlib import Path


class SecretStoreError(RuntimeError):
    """Erro ao persistir ou ler segredos da estação."""


class SecretStore:
    """Persiste valores cifrados com DPAPI de escopo da máquina.

    O arquivo é protegido pelas ACLs do diretório ProgramData; o conteúdo não
    contém valores em texto claro. O escopo da máquina permite leitura pelo
    serviço LocalSystem e pela interface administrativa elevada.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def status(self, keys: tuple[str, ...]) -> dict[str, bool]:
        values = self._read_blobs()
        return {key: bool(values.get(key)) for key in keys}

    def get(self, key: str) -> str:
        encoded = self._read_blobs().get(key)
        if not encoded:
            return ""
        try:
            encrypted = base64.b64decode(encoded.encode("ascii"), validate=True)
            return self._unprotect(encrypted).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as error:
            raise SecretStoreError(f"Segredo local inválido: {key}") from error

    def update(self, values: Mapping[str, str | None]) -> None:
        blobs = self._read_blobs()
        for key, value in values.items():
            if value is None:
                continue
            if value:
                blobs[key] = base64.b64encode(self._protect(value.encode("utf-8"))).decode("ascii")
            else:
                blobs.pop(key, None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(blobs, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    def _read_blobs(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SecretStoreError("Arquivo de segredos local inválido") from error
        if not isinstance(parsed, dict) or not all(isinstance(value, str) for value in parsed.values()):
            raise SecretStoreError("Formato de segredos local inválido")
        return parsed

    @staticmethod
    def _protect(value: bytes) -> bytes:
        if os.name != "nt":
            raise SecretStoreError("A persistência de segredos é suportada somente no Windows.")
        try:
            import win32crypt

            flags = win32crypt.CRYPTPROTECT_LOCAL_MACHINE
            return win32crypt.CryptProtectData(value, "VOXEL Router", None, None, None, flags)[1]
        except Exception as error:  # pragma: no cover - depende da DPAPI Windows
            raise SecretStoreError("Não foi possível proteger o segredo com DPAPI.") from error

    @staticmethod
    def _unprotect(value: bytes) -> bytes:
        if os.name != "nt":
            raise SecretStoreError("A leitura de segredos é suportada somente no Windows.")
        try:
            import win32crypt

            return win32crypt.CryptUnprotectData(value, None, None, None, 0)[1]
        except Exception as error:  # pragma: no cover - depende da DPAPI Windows
            raise SecretStoreError("Não foi possível abrir o segredo protegido por DPAPI.") from error
