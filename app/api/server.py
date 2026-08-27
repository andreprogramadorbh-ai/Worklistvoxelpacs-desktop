from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.config.models import ServiceSettings
from app.database.database import Database
from app.queue.dispatcher import QueueDispatcher


class WorklistCreate(BaseModel):
    patient_id: str
    patient_name: str
    accession_number: str
    scheduled_station_ae_title: str
    scheduled_start_date: str
    modality: str
    scheduled_start_time: str = ""
    scheduled_station_name: str = ""
    procedure_description: str = ""


class LocalApi:
    def __init__(self, database: Database, settings: ServiceSettings, token_path: Path) -> None:
        self.database = database
        self.settings = settings
        self.token_path = token_path
        self.token = self._load_or_create_token()
        self.app = FastAPI(title="VOXEL Router Local API", version="0.1.0", docs_url=None, redoc_url=None)
        self._routes()

    def _load_or_create_token(self) -> str:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        if self.token_path.exists():
            return self.token_path.read_text(encoding="utf-8").strip()
        token = secrets.token_urlsafe(32)
        self.token_path.write_text(token, encoding="utf-8")
        return token

    def _authorize(self, x_voxel_router_token: str = Header(default="")) -> None:
        if not secrets.compare_digest(x_voxel_router_token, self.token):
            raise HTTPException(status_code=401, detail="Token local inválido")

    def _routes(self) -> None:
        @self.app.get("/health")
        def health() -> dict:
            with self.database.connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "ok", "service": "VOXEL ROUTER", "version": "0.1.0"}

        @self.app.get("/status", dependencies=[Depends(self._authorize)])
        def status() -> dict:
            with self.database.connection() as conn:
                queue = conn.execute("SELECT status,COUNT(*) total FROM queue GROUP BY status").fetchall()
                metrics = {
                    "queue": {row["status"]: row["total"] for row in queue},
                    "worklist": conn.execute("SELECT COUNT(*) total FROM worklist WHERE status='SCHEDULED'").fetchone()["total"],
                    "modalities": conn.execute("SELECT COUNT(*) total FROM modalities WHERE active=1").fetchone()["total"],
                    "received": conn.execute("SELECT COUNT(*) total FROM dicom_instances WHERE state='RECEIVED'").fetchone()["total"],
                    "quarantine": conn.execute("SELECT COUNT(*) total FROM quarantine_items WHERE resolved_at IS NULL").fetchone()["total"],
                }
            return {"metrics": metrics, "settings": self.settings.public_dict()}

        @self.app.get("/modalities", dependencies=[Depends(self._authorize)])
        def modalities() -> list[dict]:
            with self.database.connection() as conn:
                rows = conn.execute(
                    "SELECT id,name,ae_title,host,port,modality,station_name,institution_name,active,last_echo_at,last_echo_status "
                    "FROM modalities ORDER BY active DESC,name LIMIT 500"
                ).fetchall()
            return [dict(row) for row in rows]

        @self.app.get("/logs", dependencies=[Depends(self._authorize)])
        def logs() -> list[dict]:
            with self.database.connection() as conn:
                rows = conn.execute(
                    "SELECT occurred_at,level,category,event,detail FROM system_logs ORDER BY id DESC LIMIT 500"
                ).fetchall()
            return [dict(row) for row in rows]

        @self.app.get("/audit", dependencies=[Depends(self._authorize)])
        def audit() -> list[dict]:
            with self.database.connection() as conn:
                rows = conn.execute(
                    "SELECT occurred_at,actor,event_type,category,outcome,detail FROM audit_logs ORDER BY id DESC LIMIT 500"
                ).fetchall()
            return [dict(row) for row in rows]

        @self.app.get("/quarantine", dependencies=[Depends(self._authorize)])
        def quarantine() -> list[dict]:
            with self.database.connection() as conn:
                rows = conn.execute(
                    "SELECT id,source_ae,source_ip,reason_code,reason_detail,created_at,resolved_at "
                    "FROM quarantine_items ORDER BY id DESC LIMIT 500"
                ).fetchall()
            return [dict(row) for row in rows]

        @self.app.get("/queue", dependencies=[Depends(self._authorize)])
        def queue() -> list[dict]:
            with self.database.connection() as conn:
                rows = conn.execute("SELECT id,sop_instance_uid,status,attempts,next_attempt_at,last_error FROM queue ORDER BY id DESC LIMIT 500").fetchall()
            return [dict(row) for row in rows]

        @self.app.post("/queue/{queue_id}/retry", dependencies=[Depends(self._authorize)])
        def retry(queue_id: int) -> dict:
            with self.database.transaction() as conn:
                changed = conn.execute("UPDATE queue SET status='PENDING',next_attempt_at=CURRENT_TIMESTAMP,last_error=NULL WHERE id=? AND status IN ('FAILED','RETRY','CANCELLED')", (queue_id,)).rowcount
            if not changed:
                raise HTTPException(status_code=404, detail="Item não encontrado ou não elegível")
            return {"status": "queued"}

        @self.app.get("/worklist", dependencies=[Depends(self._authorize)])
        def worklist() -> list[dict]:
            with self.database.connection() as conn:
                rows = conn.execute("SELECT patient_id,patient_name,accession_number,scheduled_station_ae_title,scheduled_start_date,scheduled_start_time,modality,procedure_description,status FROM worklist WHERE status='SCHEDULED' ORDER BY scheduled_start_date LIMIT 1000").fetchall()
            return [dict(row) for row in rows]

        @self.app.post("/worklist", dependencies=[Depends(self._authorize)])
        def create_worklist(item: WorklistCreate) -> dict:
            with self.database.transaction() as conn:
                conn.execute("INSERT INTO worklist(patient_id,patient_name,accession_number,scheduled_station_ae_title,scheduled_start_date,scheduled_start_time,modality,scheduled_station_name,procedure_description) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(accession_number,scheduled_station_ae_title) DO UPDATE SET patient_id=excluded.patient_id,patient_name=excluded.patient_name,scheduled_start_date=excluded.scheduled_start_date,scheduled_start_time=excluded.scheduled_start_time,modality=excluded.modality,procedure_description=excluded.procedure_description,updated_at=CURRENT_TIMESTAMP", (item.patient_id,item.patient_name,item.accession_number,item.scheduled_station_ae_title,item.scheduled_start_date,item.scheduled_start_time,item.modality,item.scheduled_station_name,item.procedure_description))
            return {"status": "scheduled"}

        @self.app.post("/router/dispatch", dependencies=[Depends(self._authorize)])
        def dispatch() -> dict:
            return {"processed": QueueDispatcher(self.database, self.settings).dispatch_once()}
