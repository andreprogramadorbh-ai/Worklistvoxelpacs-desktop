from __future__ import annotations

import ipaddress
import logging
from pathlib import Path
from typing import Any

from pynetdicom import AE, ALL_TRANSFER_SYNTAXES, AllStoragePresentationContexts, evt
from pynetdicom.sop_class import Verification

from app.config.models import ServiceSettings
from app.queue.spool import SpoolStore
from app.validation.dataset import validate_dataset

LOGGER = logging.getLogger(__name__)


class StorageScp:
    def __init__(self, settings: ServiceSettings, spool: SpoolStore) -> None:
        self.settings = settings
        self.spool = spool
        self._server: Any | None = None

    def start(self) -> None:
        ae = AE(ae_title=self.settings.router_ae_title)
        ae.add_supported_context(Verification)
        for context in AllStoragePresentationContexts:
            ae.add_supported_context(context.abstract_syntax, ALL_TRANSFER_SYNTAXES)
        handlers = [
            (evt.EVT_C_ECHO, self._handle_echo),
            (evt.EVT_C_STORE, self._handle_store),
            (evt.EVT_ACCEPTED, self._handle_accepted),
        ]
        self._server = ae.start_server(
            (self.settings.dicom_host, self.settings.dicom_port),
            block=False,
            evt_handlers=handlers,
            ae_title=self.settings.router_ae_title,
        )

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def _association_allowed(self, event: Any) -> bool:
        requestor = event.assoc.requestor
        ae_title = str(requestor.ae_title).strip()
        host = requestor.address
        if self.settings.allowed_calling_aes and ae_title not in self.settings.allowed_calling_aes:
            return False
        if self.settings.allowed_source_cidrs:
            address = ipaddress.ip_address(host)
            return any(address in ipaddress.ip_network(cidr, strict=False) for cidr in self.settings.allowed_source_cidrs)
        return True

    def _handle_accepted(self, event: Any) -> None:
        if not self._association_allowed(event):
            event.assoc.abort()
            LOGGER.warning("associacao_abortada_origem_nao_autorizada")

    @staticmethod
    def _handle_echo(_: Any) -> int:
        return 0x0000

    def _handle_store(self, event: Any) -> int:
        if not self._association_allowed(event):
            return 0xA801  # Refused: move destination unknown / policy rejection
        try:
            dataset = event.dataset
            dataset.file_meta = event.file_meta
            validation = validate_dataset(dataset)
            if not validation.accepted:
                LOGGER.warning("cstore_rejeitado_validacao:%s", validation.reason_code)
                return 0xC210
            source_ae = str(event.assoc.requestor.ae_title).strip()
            self.spool.persist(
                event.encoded_dataset(),
                patient_id=str(dataset.PatientID),
                accession_number=str(getattr(dataset, "AccessionNumber", "")),
                study_uid=str(dataset.StudyInstanceUID),
                series_uid=str(dataset.SeriesInstanceUID),
                sop_uid=str(dataset.SOPInstanceUID),
                sop_class_uid=str(dataset.SOPClassUID),
                modality=str(dataset.Modality),
                institution_name=str(dataset.InstitutionName),
                source_ae=source_ae,
            )
            return 0x0000
        except Exception:
            LOGGER.exception("cstore_falhou_antes_da_confirmacao")
            return 0xA700
