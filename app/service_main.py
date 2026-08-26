from __future__ import annotations

import logging
import signal
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from app.api.server import LocalApi
from app.config.models import ServiceSettings, default_config_path
from app.config.repository import SettingsRepository
from app.database.database import Database
from app.dicom.mwl.worklist_scp import WorklistScp
from app.dicom.scp.storage_scp import StorageScp
from app.queue.dispatcher import QueueDispatcher
from app.queue.spool import SpoolStore

LOGGER = logging.getLogger("voxel_router")


class RouterRuntime:
    def __init__(self, settings: ServiceSettings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.spool = SpoolStore(settings.spool_path, self.database)
        self.storage_scp = StorageScp(settings, self.spool)
        self.worklist_scp = WorklistScp(settings, self.database)
        self.stop_event = threading.Event()
        self.api_server: uvicorn.Server | None = None

    def start(self) -> None:
        self._prepare_directories()
        self.database.initialize()
        self.storage_scp.start()
        self.worklist_scp.start()
        self._start_api()
        threading.Thread(target=self._dispatch_loop, name="queue-dispatcher", daemon=True).start()
        LOGGER.info("router_service_started")

    def stop(self) -> None:
        self.stop_event.set()
        self.worklist_scp.stop()
        self.storage_scp.stop()
        if self.api_server:
            self.api_server.should_exit = True
        LOGGER.info("router_service_stopped")

    def _prepare_directories(self) -> None:
        for path in (
            self.settings.spool_path,
            self.settings.quarantine_path,
            self.settings.log_path,
            self.settings.database_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _start_api(self) -> None:
        api = LocalApi(
            self.database,
            self.settings,
            self.settings.base_path / "config" / "local-api.token",
        )
        config = uvicorn.Config(
            api.app,
            host=self.settings.local_api_host,
            port=self.settings.local_api_port,
            log_level="warning",
            log_config=None,
            access_log=False,
        )
        self.api_server = uvicorn.Server(config)
        threading.Thread(target=self.api_server.run, name="local-api", daemon=True).start()

    def _dispatch_loop(self) -> None:
        dispatcher = QueueDispatcher(self.database, self.settings)
        while not self.stop_event.wait(2):
            try:
                dispatcher.dispatch_once()
            except Exception:
                LOGGER.exception("queue_dispatcher_failure")


def load_settings(config_path: Path | None = None) -> ServiceSettings:
    """Carrega a configuração compartilhada pelo console e pelo serviço Windows."""
    return SettingsRepository(config_path or default_config_path()).load()


def configure_logging(settings: ServiceSettings) -> None:
    """Configura log rotativo durável, independente do contexto de conta do serviço."""
    settings.log_path.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if any(getattr(handler, "name", "") == "voxel-router-file" for handler in root_logger.handlers):
        return
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = RotatingFileHandler(
        settings.log_path / "router.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.name = "voxel-router-file"
    file_handler.setFormatter(formatter)
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)


def main() -> None:
    settings = load_settings()
    configure_logging(settings)
    runtime = RouterRuntime(settings)
    signal.signal(signal.SIGTERM, lambda *_: runtime.stop())
    signal.signal(signal.SIGINT, lambda *_: runtime.stop())
    runtime.start()
    try:
        while not runtime.stop_event.wait(1):
            pass
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
