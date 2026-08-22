from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.database.database import Database


@dataclass(frozen=True, slots=True)
class StoredInstance:
    sop_instance_uid: str
    sha256: str
    path: Path
    duplicate: bool


class SpoolStore:
    """Grava DICOM de forma atômica antes de confirmar sucesso ao emissor."""

    def __init__(self, root: Path, database: Database) -> None:
        self.root = root
        self.database = database

    def persist(
        self,
        encoded_dataset: bytes,
        *,
        patient_id: str,
        accession_number: str,
        study_uid: str,
        series_uid: str,
        sop_uid: str,
        sop_class_uid: str,
        modality: str,
        institution_name: str,
        source_ae: str,
    ) -> StoredInstance:
        digest = hashlib.sha256(encoded_dataset).hexdigest()
        received_at = datetime.now(timezone.utc).strftime("%Y%m%d")
        final = self.root / received_at / study_uid / series_uid / f"{sop_uid}.dcm"
        temporary = final.with_suffix(".part")
        final.parent.mkdir(parents=True, exist_ok=True)

        with self.database.transaction() as conn:
            existing = conn.execute(
                "SELECT spool_path, sha256 FROM dicom_instances WHERE sop_instance_uid = ? OR sha256 = ?",
                (sop_uid, digest),
            ).fetchone()
            if existing:
                return StoredInstance(sop_uid, existing["sha256"], Path(existing["spool_path"]), True)

            with temporary.open("wb") as handle:
                handle.write(encoded_dataset)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, final)
            try:
                conn.execute(
                    "INSERT INTO studies(study_instance_uid,patient_id,accession_number,modality,institution_name,source_ae) VALUES (?,?,?,?,?,?)",
                    (study_uid, patient_id, accession_number, modality, institution_name, source_ae),
                )
                conn.execute(
                    "INSERT INTO series(series_instance_uid,study_instance_uid,modality) VALUES (?,?,?)",
                    (series_uid, study_uid, modality),
                )
                conn.execute(
                    "INSERT INTO dicom_instances(sop_instance_uid,series_instance_uid,study_instance_uid,sop_class_uid,modality,sha256,spool_path,state) VALUES (?,?,?,?,?,?,?,?)",
                    (sop_uid, series_uid, study_uid, sop_class_uid, modality, digest, str(final), "QUEUED"),
                )
                conn.execute(
                    "INSERT INTO queue(sop_instance_uid,status) VALUES (?,?)",
                    (sop_uid, "PENDING"),
                )
            except Exception:
                final.unlink(missing_ok=True)
                raise
        return StoredInstance(sop_uid, digest, final, False)

    def quarantine(self, source: Path, quarantine_root: Path, reason: str) -> Path:
        target = quarantine_root / datetime.now(timezone.utc).strftime("%Y%m%d") / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return target
