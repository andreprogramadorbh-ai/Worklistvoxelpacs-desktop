"""Aplicativo administrativo local do VOXEL Router Desktop."""
from __future__ import annotations

import base64
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config.models import (
    CloudDicomDestination,
    PacsApiSettings,
    RisApiSettings,
    default_data_root,
)
from app.config.repository import SettingsRepository
from app.security.secret_store import SecretStore, SecretStoreError
from app.services.cloud_client import CloudApiConfig, CloudRouterClient
from desktop.local_api import LocalApiClient, LocalApiError

APP_TITLE = "VOXEL ROUTER DESKTOP"
APP_SUBTITLE = "DICOM Gateway & Modality Worklist"
SERVICE_NAME = "VOXELRouterService"


@dataclass(frozen=True)
class Metric:
    label: str
    key: str
    tone: str


class RouterWindow(QMainWindow):
    """Painel administrativo que consome somente a API local do Router."""

    def __init__(self) -> None:
        super().__init__()
        self.settings_repository = SettingsRepository(default_data_root() / "config" / "config.json")
        self.secret_store = SecretStore(default_data_root() / "config" / "secrets.dpapi.json")
        self.settings = self.settings_repository.load()
        self.api = self._create_api_client()
        self.metric_labels: dict[str, QLabel] = {}
        self.tables: dict[str, QTableWidget] = {}
        self.status_label = QLabel()
        self.config_inputs: dict[str, QWidget] = {}
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1220, 760)
        self._build()
        self._refresh()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh)
        self.refresh_timer.start(10_000)

    def _create_api_client(self) -> LocalApiClient:
        return LocalApiClient(
            default_data_root() / "config" / "local-api.token",
            self.settings.local_api_host,
            self.settings.local_api_port,
        )

    def _build(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._dashboard_page())
        self.pages.addWidget(self._table_page("Worklist", "worklist"))
        self.pages.addWidget(self._table_page("Modalidades", "modalities"))
        self.pages.addWidget(self._router_page())
        self.pages.addWidget(self._table_page("Fila", "queue", retryable=True))
        self.pages.addWidget(self._table_page("Quarentena", "quarantine"))
        self.pages.addWidget(self._table_page("Logs", "logs"))
        self.pages.addWidget(self._table_page("Auditoria", "audit"))
        self.pages.addWidget(self._settings_page())
        self.pages.addWidget(self._manual_page())
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        refresh_action = QAction("Atualizar", self)
        refresh_action.triggered.connect(self._refresh)
        self.addAction(refresh_action)

    def _sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(250)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(20, 28, 20, 20)
        brand = QLabel("VOXEL PACS\n<b>ROUTER DESKTOP</b>")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        navigation = QListWidget()
        navigation.addItems(
            [
                "Dashboard",
                "Worklist",
                "Modalidades",
                "Router",
                "Fila",
                "Quarentena",
                "Logs",
                "Auditoria",
                "Configurações",
                "Manual",
            ]
        )
        navigation.setCurrentRow(0)
        navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        navigation.currentRowChanged.connect(lambda _: self._refresh())
        layout.addWidget(navigation, 1)
        refresh = QPushButton("ATUALIZAR PAINEL")
        refresh.clicked.connect(self._refresh)
        layout.addWidget(refresh)
        exit_button = QPushButton("SAIR")
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button)
        return side

    def _page_shell(self, title: str, description: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 30)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)
        description_label = QLabel(description)
        description_label.setObjectName("pageDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        return page, layout

    def _dashboard_page(self) -> QWidget:
        page, layout = self._page_shell("Dashboard operacional", "Monitoramento local do serviço e de seus dados operacionais.")
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)
        grid = QGridLayout()
        metrics = (
            Metric("RECEBIDOS", "received", "#22c55e"),
            Metric("WORKLIST", "worklist", "#38bdf8"),
            Metric("MODALIDADES", "modalities", "#a78bfa"),
            Metric("PENDENTES", "pending", "#f59e0b"),
            Metric("FALHAS", "failed", "#ef4444"),
            Metric("QUARENTENA", "quarantine", "#fb7185"),
        )
        for index, metric in enumerate(metrics):
            card = QFrame()
            card.setObjectName("metricCard")
            card_layout = QVBoxLayout(card)
            label = QLabel(metric.label)
            label.setObjectName("metricLabel")
            value = QLabel("—")
            value.setStyleSheet(f"color:{metric.tone}; font-size:30px; font-weight:700;")
            self.metric_labels[metric.key] = value
            card_layout.addWidget(label)
            card_layout.addWidget(value)
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
        note = QLabel(
            "O Router continua recebendo DICOM mesmo quando este painel está fechado. "
            "As alterações de conexão são gravadas localmente; reinicie o serviço para aplicá-las."
        )
        note.setObjectName("info")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _table_page(self, title: str, source: str, retryable: bool = False) -> QWidget:
        page, layout = self._page_shell(title, f"Dados locais de {title.lower()} protegidos pela API do Router.")
        controls = QHBoxLayout()
        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self._refresh)
        controls.addWidget(refresh)
        if retryable:
            retry = QPushButton("REPROCESSAR ITEM SELECIONADO")
            retry.clicked.connect(self._retry_selected_queue)
            controls.addWidget(retry)
        controls.addStretch()
        layout.addLayout(controls)
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        self.tables[source] = table
        layout.addWidget(table, 1)
        return page

    def _router_page(self) -> QWidget:
        page, layout = self._page_shell("Router", "Operações do serviço Windows e conectividade local.")
        info = QTextEdit()
        info.setReadOnly(True)
        info.setObjectName("routerInfo")
        info.setPlainText(
            "C-STORE: porta 11112\nMWL C-FIND: porta 11113\nAPI local: 127.0.0.1:17841\n\n"
            "Use Configurações para alterar AE Titles, destinos e integrações."
        )
        self.router_info = info
        layout.addWidget(info)
        controls = QHBoxLayout()
        restart = QPushButton("REINICIAR SERVIÇO")
        restart.clicked.connect(self._restart_service)
        controls.addWidget(restart)
        test = QPushButton("TESTAR API LOCAL")
        test.clicked.connect(self._test_local_api)
        controls.addWidget(test)
        controls.addStretch()
        layout.addLayout(controls)
        layout.addStretch()
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Configurações", "Credenciais são protegidas por DPAPI da máquina e não são exibidas após o salvamento.")
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._add_line_input(form, "Unidade", "unit_name", self.settings.unit_name)
        self._add_line_input(form, "AE Title do Router", "router_ae_title", self.settings.router_ae_title)
        self._add_spin_input(form, "Porta C-STORE", "dicom_port", self.settings.dicom_port, 1, 65535)
        self._add_spin_input(form, "Porta MWL", "mwl_port", self.settings.mwl_port, 1, 65535)
        self._add_line_input(form, "AEs emissores permitidos (vírgula)", "allowed_aes", ", ".join(self.settings.allowed_calling_aes))
        self._add_line_input(form, "IPs/CIDRs permitidos (vírgula)", "allowed_cidrs", ", ".join(self.settings.allowed_source_cidrs))

        section_ris = QLabel("Integração API-RIS")
        section_ris.setObjectName("sectionTitle")
        form.addRow(section_ris)
        self._add_checkbox(form, "Ativar sincronização RIS", "ris_enabled", self.settings.ris.enabled)
        self._add_line_input(form, "URL base da API-RIS", "ris_url", self.settings.ris.base_url)
        self._add_line_input(form, "Identificador deste Router", "ris_device", self.settings.ris.device_id)
        self._add_secret_input(form, "Token Bearer API-RIS", "ris_token")

        section_pacs = QLabel("Integração PACS Hetzner / Orthanc")
        section_pacs.setObjectName("sectionTitle")
        form.addRow(section_pacs)
        self._add_checkbox(form, "Ativar integração REST PACS", "pacs_enabled", self.settings.pacs.enabled)
        self._add_line_input(form, "URL base Orthanc", "pacs_url", self.settings.pacs.base_url)
        self._add_line_input(form, "Usuário Orthanc", "pacs_username", self.settings.pacs.username)
        self._add_secret_input(form, "Senha Orthanc", "pacs_password")
        self._add_checkbox(form, "Validar certificado TLS", "pacs_verify_tls", self.settings.pacs.verify_tls)

        section_destination = QLabel("Destino DICOM")
        section_destination.setObjectName("sectionTitle")
        form.addRow(section_destination)
        self._add_line_input(form, "Host PACS DICOM", "cloud_host", self.settings.cloud.host)
        self._add_spin_input(form, "Porta PACS DICOM", "cloud_port", self.settings.cloud.port, 1, 65535)
        self._add_line_input(form, "Called AE PACS", "cloud_called_ae", self.settings.cloud.called_ae_title)
        self._add_line_input(form, "Nome TLS", "cloud_tls_name", self.settings.cloud.tls_server_name)
        mode = QComboBox()
        mode.addItems(["disabled", "required"])
        mode.setCurrentText(self.settings.cloud.tls_mode)
        self.config_inputs["cloud_tls_mode"] = mode
        form.addRow("TLS DICOM", mode)
        layout.addLayout(form)
        controls = QHBoxLayout()
        save = QPushButton("SALVAR CONFIGURAÇÕES")
        save.clicked.connect(self._save_settings)
        controls.addWidget(save)
        restart = QPushButton("SALVAR E REINICIAR")
        restart.clicked.connect(self._save_and_restart)
        controls.addWidget(restart)
        test_ris = QPushButton("TESTAR API-RIS")
        test_ris.clicked.connect(self._test_ris)
        controls.addWidget(test_ris)
        test_pacs = QPushButton("TESTAR PACS REST")
        test_pacs.clicked.connect(self._test_pacs)
        controls.addWidget(test_pacs)
        controls.addStretch()
        layout.addLayout(controls)
        layout.addStretch()
        return page

    def _manual_page(self) -> QWidget:
        page, layout = self._page_shell("Manual", "Resumo de operação segura do VOXEL Router.")
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "1. Configure os AE Titles e as allowlists antes de conectar uma modalidade.\n\n"
            "2. Use a porta 11113 para Modality Worklist (C-FIND) e 11112 para envio C-STORE.\n\n"
            "3. Cadastre a URL REST do Orthanc da Hetzner e suas credenciais apenas na tela Configurações. "
            "A senha fica protegida com DPAPI e não retorna à tela depois de salva.\n\n"
            "4. A API-RIS precisa implementar os contratos /api/router/v1/config, /worklist/sync e /events. "
            "Insira o token Bearer e o identificador do dispositivo autorizados.\n\n"
            "5. Reinicie o serviço após mudanças de configuração."
        )
        layout.addWidget(text, 1)
        return page

    def _add_line_input(self, form: QFormLayout, label: str, key: str, value: str) -> None:
        input_field = QLineEdit(value)
        self.config_inputs[key] = input_field
        form.addRow(label, input_field)

    def _add_secret_input(self, form: QFormLayout, label: str, key: str) -> None:
        input_field = QLineEdit()
        input_field.setEchoMode(QLineEdit.EchoMode.Password)
        input_field.setPlaceholderText("Mantido sem alteração quando deixado em branco")
        self.config_inputs[key] = input_field
        form.addRow(label, input_field)

    def _add_spin_input(
        self, form: QFormLayout, label: str, key: str, value: int, minimum: int, maximum: int
    ) -> None:
        input_field = QSpinBox()
        input_field.setRange(minimum, maximum)
        input_field.setValue(value)
        self.config_inputs[key] = input_field
        form.addRow(label, input_field)

    def _add_checkbox(self, form: QFormLayout, label: str, key: str, value: bool) -> None:
        input_field = QCheckBox()
        input_field.setChecked(value)
        self.config_inputs[key] = input_field
        form.addRow(label, input_field)

    def _refresh(self) -> None:
        self.settings = self.settings_repository.load()
        self.api = self._create_api_client()
        try:
            health = self.api.health()
            status = self.api.status()
            self.status_label.setText(
                f"● Serviço ativo   ● API local online   ● Versão {health.get('version', '—')}"
            )
            self.status_label.setStyleSheet("color:#4ade80;")
            metrics = status.get("metrics", {})
            queue = metrics.get("queue", {})
            values = {
                "received": metrics.get("received", 0),
                "worklist": metrics.get("worklist", 0),
                "modalities": metrics.get("modalities", 0),
                "pending": queue.get("PENDING", 0) + queue.get("RETRY", 0),
                "failed": queue.get("FAILED", 0),
                "quarantine": metrics.get("quarantine", 0),
            }
            for key, label in self.metric_labels.items():
                label.setText(str(values.get(key, 0)))
            self._populate_table("worklist", self.api.worklist())
            self._populate_table("modalities", self.api.modalities())
            self._populate_table("queue", self.api.queue())
            self._populate_table("logs", self.api.logs())
            self._populate_table("audit", self.api.audit())
            self._populate_table("quarantine", self.api.quarantine())
            self.router_info.setPlainText(self._router_summary(status))
        except (LocalApiError, AttributeError) as error:
            self.status_label.setText("● Serviço ou API local indisponível")
            self.status_label.setStyleSheet("color:#f87171;")
            self.router_info.setPlainText(f"Não foi possível consultar o serviço local.\n\n{error}")

    @staticmethod
    def _router_summary(status: dict[str, Any]) -> str:
        settings = status.get("settings", {})
        cloud = settings.get("cloud", {})
        return (
            f"Serviço Windows: {SERVICE_NAME}\n"
            f"C-STORE: {settings.get('dicom_host', '0.0.0.0')}:{settings.get('dicom_port', '—')}\n"
            f"MWL C-FIND: {settings.get('dicom_host', '0.0.0.0')}:{settings.get('mwl_port', '—')}\n"
            f"API local: {settings.get('local_api_host', '127.0.0.1')}:{settings.get('local_api_port', '—')}\n"
            f"Destino DICOM: {cloud.get('host') or 'não configurado'}:{cloud.get('port', '—')}\n"
            f"Diretório de dados: {settings.get('base_path', '—')}"
        )

    def _populate_table(self, name: str, rows: list[dict[str, Any]]) -> None:
        table = self.tables.get(name)
        if table is None:
            return
        headers = list(rows[0].keys()) if rows else []
        table.clear()
        table.setRowCount(len(rows))
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        for row_index, row in enumerate(rows):
            for column_index, header in enumerate(headers):
                table.setItem(row_index, column_index, QTableWidgetItem(str(row.get(header, ""))))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

    def _retry_selected_queue(self) -> None:
        table = self.tables["queue"]
        selected = table.selectedItems()
        if not selected:
            self._warning("Fila", "Selecione um item da fila para reprocessar.")
            return
        queue_id = table.item(selected[0].row(), 0).text()
        try:
            self.api.retry_queue_item(int(queue_id))
        except (ValueError, LocalApiError) as error:
            self._warning("Fila", str(error))
            return
        self._information("Fila", "Item enviado para nova tentativa.")
        self._refresh()

    def _save_and_restart(self) -> None:
        if self._save_settings(show_message=False):
            self._restart_service()

    def _save_settings(self, show_message: bool = True) -> bool:
        try:
            self.settings.unit_name = self._line_value("unit_name")
            self.settings.router_ae_title = self._line_value("router_ae_title").upper()
            self.settings.dicom_port = self._spin_value("dicom_port")
            self.settings.mwl_port = self._spin_value("mwl_port")
            self.settings.allowed_calling_aes = self._csv_value("allowed_aes", upper=True)
            self.settings.allowed_source_cidrs = self._csv_value("allowed_cidrs")
            self.settings.ris = RisApiSettings(
                enabled=self._check_value("ris_enabled"),
                base_url=self._line_value("ris_url").rstrip("/"),
                device_id=self._line_value("ris_device"),
                timeout_seconds=self.settings.ris.timeout_seconds,
            )
            self.settings.pacs = PacsApiSettings(
                enabled=self._check_value("pacs_enabled"),
                base_url=self._line_value("pacs_url").rstrip("/"),
                username=self._line_value("pacs_username"),
                timeout_seconds=self.settings.pacs.timeout_seconds,
                verify_tls=self._check_value("pacs_verify_tls"),
            )
            self.settings.cloud = CloudDicomDestination(
                host=self._line_value("cloud_host"),
                port=self._spin_value("cloud_port"),
                called_ae_title=self._line_value("cloud_called_ae").upper(),
                calling_ae_title=self.settings.router_ae_title,
                tls_mode=self._combo_value("cloud_tls_mode"),
                tls_server_name=self._line_value("cloud_tls_name"),
            )
            self.settings_repository.save(self.settings)
            self.secret_store.update(
                {
                    "ris_bearer_token": self._line_value("ris_token"),
                    "pacs_password": self._line_value("pacs_password"),
                }
            )
        except (OSError, ValueError, SecretStoreError) as error:
            self._warning("Configurações", f"Não foi possível salvar: {error}")
            return False
        if show_message:
            self._information("Configurações", "Configurações salvas. Reinicie o serviço para aplicá-las.")
        return True

    def _restart_service(self) -> None:
        try:
            subprocess.run(["sc.exe", "stop", SERVICE_NAME], check=False, capture_output=True, text=True)
            time.sleep(2)
            started = subprocess.run(
                ["sc.exe", "start", SERVICE_NAME], check=False, capture_output=True, text=True
            )
            if started.returncode != 0 and "already running" not in started.stdout.lower():
                raise RuntimeError(started.stderr or started.stdout or "Falha ao iniciar o serviço.")
        except OSError as error:
            self._warning("Router", f"Não foi possível controlar o serviço Windows: {error}")
            return
        time.sleep(3)
        self._refresh()
        self._information("Router", "Comando de reinicialização enviado ao serviço Windows.")

    def _test_local_api(self) -> None:
        try:
            health = self.api.health()
            self._information("API local", f"API disponível. Versão: {health.get('version', '—')}")
        except LocalApiError as error:
            self._warning("API local", str(error))

    def _test_ris(self) -> None:
        if not self._save_settings(show_message=False):
            return
        if not self.settings.ris.base_url or not self.settings.ris.device_id:
            self._warning("API-RIS", "Informe a URL base e o identificador do Router antes do teste.")
            return
        try:
            token = self.secret_store.get("ris_bearer_token")
            if not token:
                raise SecretStoreError("Informe o token Bearer da API-RIS.")
            client = CloudRouterClient(
                CloudApiConfig(
                    self.settings.ris.base_url,
                    self.settings.ris.device_id,
                    token,
                    self.settings.ris.timeout_seconds,
                )
            )
            client.get_config()
        except (ConnectionError, RuntimeError, SecretStoreError) as error:
            self._warning("API-RIS", f"Teste não concluído: {error}")
            return
        self._information("API-RIS", "Conexão validada com sucesso.")

    def _test_pacs(self) -> None:
        if not self._save_settings(show_message=False):
            return
        if not self.settings.pacs.base_url:
            self._warning("PACS Hetzner", "Informe a URL base do Orthanc antes do teste.")
            return
        try:
            password = self.secret_store.get("pacs_password")
            credentials = f"{self.settings.pacs.username}:{password}".encode()
            request = urllib.request.Request(
                self.settings.pacs.base_url.rstrip("/") + "/system",
                headers={"Authorization": "Basic " + base64.b64encode(credentials).decode("ascii")},
            )
            with urllib.request.urlopen(request, timeout=self.settings.pacs.timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Orthanc respondeu HTTP {response.status}.")
        except (OSError, urllib.error.URLError, RuntimeError, SecretStoreError) as error:
            self._warning("PACS Hetzner", f"Teste não concluído: {error}")
            return
        self._information("PACS Hetzner", "Conexão REST com Orthanc validada com sucesso.")

    def _line_value(self, key: str) -> str:
        return self.config_inputs[key].text().strip()  # type: ignore[union-attr]

    def _spin_value(self, key: str) -> int:
        return self.config_inputs[key].value()  # type: ignore[union-attr]

    def _check_value(self, key: str) -> bool:
        return self.config_inputs[key].isChecked()  # type: ignore[union-attr]

    def _combo_value(self, key: str) -> str:
        return self.config_inputs[key].currentText()  # type: ignore[union-attr]

    def _csv_value(self, key: str, upper: bool = False) -> list[str]:
        values = [value.strip() for value in self._line_value(key).split(",") if value.strip()]
        return [value.upper() for value in values] if upper else values

    def _information(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QWidget { background:#0b1220; color:#e5edf9; font-family:Segoe UI,Arial; font-size:13px; }
        #sidebar { background:#111b2e; border-right:1px solid #26344c; }
        #brand { color:#58d5ff; font-size:20px; line-height:1.3; }
        #subtitle, #pageDescription, #info { color:#94a3b8; }
        #pageTitle { font-size:28px; font-weight:700; }
        #sectionTitle { color:#58d5ff; font-size:16px; font-weight:700; margin-top:16px; }
        QListWidget { background:transparent; border:0; color:#cbd5e1; outline:0; }
        QListWidget::item { padding:11px 10px; border-radius:6px; }
        QListWidget::item:selected { background:#0e7490; color:white; }
        QPushButton { background:#164e63; border:1px solid #0e7490; padding:9px 12px; border-radius:6px; font-weight:700; }
        QPushButton:hover { background:#0e7490; }
        QLineEdit, QSpinBox, QComboBox { background:#111b2e; border:1px solid #334155; border-radius:5px; padding:7px; }
        QTableWidget, QTextEdit { background:#111b2e; border:1px solid #26344c; border-radius:8px; gridline-color:#26344c; }
        QHeaderView::section { background:#1e293b; color:#cbd5e1; padding:7px; border:0; }
        QTableWidget::item:alternate { background:#101a2d; }
        #metricCard { background:#111b2e; border:1px solid #26344c; border-radius:10px; min-height:110px; }
        #metricLabel { color:#94a3b8; font-size:11px; font-weight:700; }
        """
    )
    window = RouterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
