"""Instalador gráfico do pacote Windows do VOXEL Router."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_TITLE = "Instalação do VOXEL Router"


def package_root() -> Path:
    """Retorna a raiz do pacote tanto no código-fonte quanto no executável congelado."""
    if getattr(sys, "frozen", False):
        executable_directory = Path(sys.executable).resolve().parent
        if (executable_directory / "service").exists():
            return executable_directory
        return executable_directory.parent
    return Path(__file__).resolve().parent.parent


def is_administrator() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


class SetupWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.root = package_root()
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(760, 540)
        self._build()

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 34, 36, 30)
        layout.setSpacing(14)

        brand = QLabel("VOXEL PACS\n<b>ROUTER DESKTOP</b>")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        title = QLabel("Instalar Router DICOM e painel visual")
        title.setObjectName("title")
        layout.addWidget(title)
        description = QLabel(
            "Este assistente instala o serviço Windows, o receptor DICOM C-STORE, o Worklist MWL "
            "e o painel administrativo local. O recebimento DICOM continuará ativo quando a janela for fechada."
        )
        description.setWordWrap(True)
        description.setObjectName("description")
        layout.addWidget(description)

        checklist = QFrame()
        checklist.setObjectName("card")
        checklist_layout = QVBoxLayout(checklist)
        checklist_layout.addWidget(QLabel("Componentes incluídos"))
        checklist_layout.addWidget(QLabel("• Serviço Windows VOXELRouterService com reinício automático"))
        checklist_layout.addWidget(QLabel("• C-STORE na porta 11112 e Worklist MWL na porta 11113"))
        checklist_layout.addWidget(QLabel("• Painel visual: status, Worklist, fila, logs e configurações"))
        checklist_layout.addWidget(QLabel("• Integrações seguras para API-RIS e PACS/Orthanc Hetzner"))
        layout.addWidget(checklist)

        self.firewall = QCheckBox("Liberar portas 11112 (C-STORE) e 11113 (Worklist MWL) no Firewall do Windows")
        self.firewall.setChecked(True)
        layout.addWidget(self.firewall)
        self.keep_config = QCheckBox("Preservar configuração local existente, se houver")
        self.keep_config.setChecked(True)
        layout.addWidget(self.keep_config)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(110)
        self.output.setPlainText("Pronto para instalar. O Windows solicitará confirmação administrativa.")
        layout.addWidget(self.output)

        buttons = QHBoxLayout()
        install = QPushButton("INSTALAR E ABRIR PAINEL")
        install.clicked.connect(self._install)
        buttons.addWidget(install)
        repair = QPushButton("REPARAR E TESTAR")
        repair.clicked.connect(self._repair)
        buttons.addWidget(repair)
        open_folder = QPushButton("ABRIR PASTA")
        open_folder.clicked.connect(self._open_folder)
        buttons.addWidget(open_folder)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.setCentralWidget(root)

    def _install(self) -> None:
        arguments: list[str] = []
        if self.firewall.isChecked():
            arguments.append("-OpenFirewallRule")
        if not self.keep_config.isChecked():
            arguments.append("-OverwriteConfig")
        if self._run_script("install.ps1", arguments):
            self._launch_desktop()

    def _repair(self) -> None:
        self._run_script("repair.ps1", [])

    def _run_script(self, name: str, arguments: list[str]) -> bool:
        script = self.root / name
        if not script.exists():
            self._error(f"Arquivo necessário não encontrado: {script}")
            return False
        if not is_administrator():
            self._error("Execute este instalador como administrador.")
            return False
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *arguments,
        ]
        self.output.setPlainText("Executando instalação. Aguarde...")
        QApplication.processEvents()
        try:
            result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=False)
        except OSError as error:
            self._error(f"Não foi possível iniciar o PowerShell: {error}")
            return False
        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        self.output.setPlainText(output or "Operação concluída sem mensagens adicionais.")
        if result.returncode != 0:
            self._error("A operação não foi concluída. Consulte o registro exibido nesta tela.")
            return False
        QMessageBox.information(self, APP_TITLE, "Operação concluída com sucesso.")
        return True

    def _launch_desktop(self) -> None:
        executable = Path(r"C:\Program Files\VOXEL\Router\desktop\VOXELRouterDesktop.exe")
        if executable.exists():
            subprocess.Popen([str(executable)])
        else:
            self._error("Painel instalado, mas o executável visual não foi localizado.")

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root)))

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, APP_TITLE, message)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QWidget { background:#0b1220; color:#e5edf9; font-family:Segoe UI,Arial; font-size:13px; }
        #brand { color:#58d5ff; font-size:20px; line-height:1.3; }
        #title { font-size:26px; font-weight:700; }
        #description { color:#cbd5e1; font-size:14px; }
        #card { background:#111b2e; border:1px solid #26344c; border-radius:10px; padding:12px; }
        QTextEdit { background:#111b2e; border:1px solid #334155; border-radius:7px; color:#cbd5e1; }
        QPushButton { background:#164e63; border:1px solid #0e7490; padding:10px 14px; border-radius:6px; font-weight:700; }
        QPushButton:hover { background:#0e7490; }
        """
    )
    window = SetupWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
