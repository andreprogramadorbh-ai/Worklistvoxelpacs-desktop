"""Hospedagem do VOXEL Router no Windows Service Control Manager."""
from __future__ import annotations

import logging
import os

from app.service_main import RouterRuntime, configure_logging, load_settings

LOGGER = logging.getLogger("voxel_router.windows_service")


if os.name == "nt":
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class VOXELRouterWindowsService(win32serviceutil.ServiceFramework):
        """Serviço Windows responsável pelo ciclo de vida do Router."""

        _svc_name_ = "VOXELRouterService"
        _svc_display_name_ = "VOXEL Router Service"
        _svc_description_ = "Recebimento DICOM e fila local do VOXEL PACS."

        def __init__(self, args: list[str]) -> None:
            super().__init__(args)
            self.stop_handle = win32event.CreateEvent(None, 0, 0, None)
            self.runtime: RouterRuntime | None = None

        def SvcStop(self) -> None:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self.runtime:
                self.runtime.stop()
            win32event.SetEvent(self.stop_handle)

        def SvcDoRun(self) -> None:
            settings = load_settings()
            configure_logging(settings)
            self.runtime = RouterRuntime(settings)
            try:
                self.runtime.start()
                servicemanager.LogInfoMsg("VOXEL Router Service iniciado")
                win32event.WaitForSingleObject(self.stop_handle, win32event.INFINITE)
            except Exception:
                LOGGER.exception("windows_service_failure")
                servicemanager.LogErrorMsg("VOXEL Router Service falhou durante a inicialização")
                raise
            finally:
                if self.runtime:
                    self.runtime.stop()


def main() -> None:
    """Ponto de entrada empacotado somente para Windows."""
    if os.name != "nt":
        raise RuntimeError("O serviço Windows do VOXEL Router só pode ser executado no Windows.")
    win32serviceutil.HandleCommandLine(VOXELRouterWindowsService)


if __name__ == "__main__":
    main()
