from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

APP_TITLE = "VOXEL ROUTER DESKTOP"
APP_SUBTITLE = "DICOM Gateway & Modality Worklist"


@dataclass(frozen=True)
class Metric:
    label: str
    value: str
    tone: str = "#22c55e"


class RouterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1180, 720)
        self._build()

    def _build(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._dashboard())
        for title in ("Worklist", "Modalidades", "Router", "Fila", "Quarentena", "Logs", "Auditoria", "Configurações", "Manual"):
            self.pages.addWidget(self._placeholder(title))
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

    def _sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(255)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(22, 28, 22, 22)
        brand = QLabel("VOXEL PACS\n<b>ROUTER DESKTOP</b>")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        navigation = QListWidget()
        navigation.addItems(["Dashboard", "Worklist", "Modalidades", "Router", "Fila", "Quarentena", "Logs", "Auditoria", "Configurações", "Manual"])
        navigation.setCurrentRow(0)
        navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        layout.addWidget(navigation, 1)
        logout = QPushButton("SAIR")
        logout.clicked.connect(self.close)
        layout.addWidget(logout)
        return side

    def _dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 34, 40, 34)
        title = QLabel("Dashboard operacional")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        status = QLabel("● Router Online     ● Worklist Online     ● DICOM SCP Online     ● VOXEL Cloud Online")
        status.setObjectName("status")
        layout.addWidget(status)
        metrics = QHBoxLayout()
        for metric in (Metric("RECEBIDOS", "0"), Metric("ENVIADOS", "0"), Metric("PENDENTES", "0", "#f59e0b"), Metric("FALHAS", "0", "#ef4444"), Metric("MODALIDADES", "0", "#38bdf8")):
            card = QFrame()
            card.setObjectName("metricCard")
            card_layout = QVBoxLayout(card)
            label = QLabel(metric.label)
            label.setObjectName("metricLabel")
            value = QLabel(metric.value)
            value.setStyleSheet(f"color: {metric.tone}; font-size: 32px; font-weight: 700;")
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            metrics.addWidget(card)
        layout.addLayout(metrics)
        info = QLabel("O painel administra o serviço local. O processamento DICOM continua ativo mesmo com esta janela fechada.")
        info.setWordWrap(True)
        info.setObjectName("info")
        layout.addWidget(info)
        layout.addStretch()
        return page

    @staticmethod
    def _placeholder(title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 34, 40, 34)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        body = QLabel("Módulo preparado para integração com a API local do serviço VOXEL Router.")
        body.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addStretch()
        return page


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet("""
      QWidget { background:#0b1220; color:#e5edf9; font-family:Segoe UI,Arial; }
      #sidebar { background:#111b2e; border-right:1px solid #26344c; }
      #brand { color:#58d5ff; font-size:20px; line-height:1.3; }
      #subtitle { color:#94a3b8; font-size:11px; margin-bottom:18px; }
      QListWidget { background:transparent; border:0; color:#cbd5e1; outline:0; }
      QListWidget::item { padding:11px 10px; border-radius:6px; }
      QListWidget::item:selected { background:#0e7490; color:white; }
      QPushButton { background:#164e63; border:1px solid #0e7490; padding:10px; border-radius:6px; font-weight:700; }
      #pageTitle { font-size:28px; font-weight:700; }
      #status { color:#4ade80; margin:8px 0 22px; }
      #metricCard { background:#111b2e; border:1px solid #26344c; border-radius:10px; min-height:118px; }
      #metricLabel { color:#94a3b8; font-size:11px; font-weight:700; }
      #info { color:#94a3b8; margin-top:26px; }
    """)
    window = RouterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
