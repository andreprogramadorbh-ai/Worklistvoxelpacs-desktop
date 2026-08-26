import socket
import subprocess
import sys
import time
from pathlib import Path

from app.config.models import ServiceSettings
from app.service_main import RouterRuntime


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_synthetic_client_completes_echo_and_store(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VOXEL_ROUTER_DATA_ROOT", str(tmp_path))
    dicom_port = free_port()
    settings = ServiceSettings(
        router_ae_title="VOXEL_ROUTER",
        dicom_host="127.0.0.1",
        dicom_port=dicom_port,
        mwl_port=free_port(),
        local_api_host="127.0.0.1",
        local_api_port=free_port(),
        allowed_calling_aes=["VOXEL_TEST_SCU"],
        allowed_source_cidrs=["127.0.0.1/32"],
    )
    runtime = RouterRuntime(settings)
    runtime.start()
    client = Path(__file__).parents[1] / "tools" / "test_reception.py"

    try:
        time.sleep(0.2)
        result = subprocess.run(
            [
                sys.executable,
                str(client),
                "--host",
                "127.0.0.1",
                "--port",
                str(dicom_port),
                "--called-ae",
                "VOXEL_ROUTER",
                "--calling-ae",
                "VOXEL_TEST_SCU",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    finally:
        runtime.stop()

    assert result.returncode == 0, result.stderr
    assert "RECEPCAO_DICOM_OK" in result.stdout
