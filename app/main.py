from __future__ import annotations

from app.service_main import main as service_main


def main() -> None:
    """Entrada do motor; o painel PySide6 será iniciado por atalho separado no Windows."""
    service_main()


if __name__ == "__main__":
    main()
