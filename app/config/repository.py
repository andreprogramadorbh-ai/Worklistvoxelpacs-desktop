from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from app.config.models import CloudDicomDestination, ServiceSettings


class SettingsRepository:
    """Armazena somente parâmetros não secretos em JSON local com escrita atômica."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> ServiceSettings:
        if not self.path.exists():
            return ServiceSettings()
        # Windows PowerShell 5.1 escreve UTF-8 com BOM; utf-8-sig aceita ambos os formatos.
        raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        cloud = CloudDicomDestination(**raw.pop("cloud", {}))
        return ServiceSettings(cloud=cloud, **raw)

    def save(self, settings: ServiceSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
