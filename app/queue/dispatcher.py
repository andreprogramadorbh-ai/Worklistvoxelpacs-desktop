from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydicom import dcmread
from pynetdicom import AE, ALL_TRANSFER_SYNTAXES, AllStoragePresentationContexts
from pynetdicom.sop_class import Verification

from app.config.models import ServiceSettings
from app.database.database import Database

LOGGER = logging.getLogger(__name__)


class QueueDispatcher:
    def __init__(self, database: Database, settings: ServiceSettings) -> None:
        self.database = database
        self.settings = settings

    def dispatch_once(self) -> bool:
        with self.database.transaction() as conn:
            item = conn.execute(
                """SELECT q.id,q.sop_instance_uid,q.attempts,i.spool_path
                   FROM queue q JOIN dicom_instances i ON i.sop_instance_uid=q.sop_instance_uid
                   WHERE q.status IN ('PENDING','RETRY') AND q.next_attempt_at <= CURRENT_TIMESTAMP
                   ORDER BY q.priority ASC,q.created_at ASC LIMIT 1"""
            ).fetchone()
            if not item:
                return False
            conn.execute(
                "UPDATE queue SET status='LEASED',attempts=attempts+1,leased_until=datetime('now','+5 minutes'),updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (item["id"],),
            )
            attempt_no = item["attempts"] + 1
            conn.execute(
                "INSERT INTO queue_attempts(queue_id,attempt_no,status) VALUES (?,?,?)",
                (item["id"], attempt_no, "STARTED"),
            )
        success, status, detail = self._send(Path(item["spool_path"]))
        with self.database.transaction() as conn:
            if success:
                conn.execute("UPDATE queue SET status='SENT',leased_until=NULL,last_error=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (item["id"],))
                conn.execute("UPDATE dicom_instances SET state='SENT',sent_at=CURRENT_TIMESTAMP WHERE sop_instance_uid=?", (item["sop_instance_uid"],))
                conn.execute("UPDATE queue_attempts SET completed_at=CURRENT_TIMESTAMP,status='SENT',dicom_status=? WHERE queue_id=? AND attempt_no=?", (status, item["id"], attempt_no))
            else:
                delay = min(self.settings.retry_base_seconds * (2 ** min(attempt_no, 10)), self.settings.retry_max_seconds)
                retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).strftime("%Y-%m-%d %H:%M:%S")
                final = attempt_no >= self.settings.max_retry
                conn.execute(
                    "UPDATE queue SET status=?,leased_until=NULL,next_attempt_at=?,last_error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    ("FAILED" if final else "RETRY", retry_at, detail[:1000], item["id"]),
                )
                conn.execute("UPDATE dicom_instances SET state=? WHERE sop_instance_uid=?", ("FAILED" if final else "QUEUED", item["sop_instance_uid"]))
                conn.execute("UPDATE queue_attempts SET completed_at=CURRENT_TIMESTAMP,status=?,dicom_status=?,error_message=? WHERE queue_id=? AND attempt_no=?", ("FAILED" if final else "RETRY", status, detail[:1000], item["id"], attempt_no))
        return True

    def _send(self, path: Path) -> tuple[bool, int | None, str]:
        destination = self.settings.cloud
        if not destination.host:
            return False, None, "Destino Cloud não configurado"
        try:
            dataset = dcmread(path)
            ae = AE(ae_title=destination.calling_ae_title)
            ae.add_requested_context(Verification)
            for context in AllStoragePresentationContexts:
                ae.add_requested_context(context.abstract_syntax, ALL_TRANSFER_SYNTAXES)
            assoc = ae.associate(
                destination.host,
                destination.port,
                ae_title=destination.called_ae_title,
                acse_timeout=self.settings.association_timeout_seconds,
                dimse_timeout=self.settings.dimse_timeout_seconds,
                network_timeout=self.settings.network_timeout_seconds,
            )
            if not assoc.is_established:
                return False, None, "Associação Cloud rejeitada ou indisponível"
            try:
                status = assoc.send_c_store(dataset)
                status_code = int(getattr(status, "Status", 0xC000))
                return status_code == 0x0000, status_code, f"DIMSE status 0x{status_code:04X}"
            finally:
                assoc.release()
        except Exception as error:
            LOGGER.exception("envio_cloud_falhou")
            return False, None, type(error).__name__
