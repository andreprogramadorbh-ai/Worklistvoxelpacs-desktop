"""Configuração central do VOXEL Router Desktop.

Segredos ficam fora deste arquivo e devem ser protegidos por DPAPI no Windows.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from platformdirs import user_data_dir

APP_NAME = "VOXEL ROUTER DESKTOP"
APP_VENDOR = "VOXEL PACS"
CONFIG_VERSION = 1


@dataclass(slots=True)
class CloudDicomDestination:
    host: str = ""
    port: int = 4242
    called_ae_title: str = "VOXELSRVPACS"
    calling_ae_title: str = "VOXEL_ROUTER"
    tls_mode: Literal["disabled", "required"] = "disabled"
    tls_server_name: str = ""


@dataclass(slots=True)
class ServiceSettings:
    unit_name: str = ""
    router_ae_title: str = "VOXEL_ROUTER"
    dicom_host: str = "0.0.0.0"
    dicom_port: int = 11112
    mwl_port: int = 11113
    local_api_host: str = "127.0.0.1"
    local_api_port: int = 17841
    max_retry: int = 12
    retry_base_seconds: int = 30
    retry_max_seconds: int = 3600
    association_timeout_seconds: int = 20
    dimse_timeout_seconds: int = 90
    network_timeout_seconds: int = 30
    retention_after_delivery_days: int = 7
    quarantine_policy: Literal["quarantine", "reject"] = "quarantine"
    allowed_calling_aes: list[str] = field(default_factory=list)
    allowed_source_cidrs: list[str] = field(default_factory=list)
    cloud: CloudDicomDestination = field(default_factory=CloudDicomDestination)

    @property
    def base_path(self) -> Path:
        return Path(user_data_dir("VOXELRouter", APP_VENDOR, roaming=False))

    @property
    def database_path(self) -> Path:
        return self.base_path / "database" / "router.sqlite3"

    @property
    def spool_path(self) -> Path:
        return self.base_path / "spool"

    @property
    def quarantine_path(self) -> Path:
        return self.base_path / "quarantine"

    @property
    def log_path(self) -> Path:
        return self.base_path / "logs"

    def public_dict(self) -> dict:
        data = asdict(self)
        data["base_path"] = str(self.base_path)
        data["database_path"] = str(self.database_path)
        return data


def validate_ae_title(value: str) -> str:
    value = value.strip().upper()
    if not value or len(value) > 16:
        raise ValueError("AE Title deve conter entre 1 e 16 caracteres")
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("AE Title deve usar apenas caracteres ASCII imprimíveis")
    return value
