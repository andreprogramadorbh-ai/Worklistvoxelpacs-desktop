from pathlib import Path

from app.config.models import default_config_path, default_data_root
from app.config.repository import SettingsRepository
from app.service_main import load_settings


def test_config_path_uses_explicit_data_root(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VOXEL_ROUTER_DATA_ROOT", str(tmp_path))

    assert default_data_root() == tmp_path
    assert default_config_path() == tmp_path / "config" / "config.json"


def test_service_loads_shared_config_path(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VOXEL_ROUTER_DATA_ROOT", str(tmp_path))
    config_path = default_config_path()
    repository = SettingsRepository(config_path)
    settings = load_settings()

    assert settings.base_path == tmp_path
    repository.save(settings)
    assert config_path.exists()


def test_settings_repository_accepts_windows_utf8_bom(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_bytes(b'\xef\xbb\xbf{"router_ae_title": "VOXEL_ROUTER"}')

    settings = SettingsRepository(config_path).load()

    assert settings.router_ae_title == "VOXEL_ROUTER"
