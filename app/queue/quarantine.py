from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.database.database import Database


class QuarantineStore:
    def __init__(self, root: Path, database: Database) -> None:
        self.root = root
        self.database = database

    def persist(self, encoded_dataset: bytes, *, source_ae: str, source_ip: str, reason_code: str, reason_detail: str) -> Path:
        directory = self.root / datetime.now(timezone.utc).strftime("%Y%m%d")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid.uuid4()}.dcm"
        temp = path.with_suffix(".part")
        with temp.open("wb") as handle:
            handle.write(encoded_dataset)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        with self.database.transaction() as conn:
            conn.execute(
                "INSERT INTO quarantine_items(spool_path,source_ae,source_ip,reason_code,reason_detail) VALUES (?,?,?,?,?)",
                (str(path), source_ae, source_ip, reason_code, reason_detail[:1000]),
            )
        return path
