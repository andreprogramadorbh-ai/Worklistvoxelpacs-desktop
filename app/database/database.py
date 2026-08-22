from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS modalities (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  ae_title TEXT NOT NULL UNIQUE,
  host TEXT NOT NULL,
  port INTEGER NOT NULL,
  modality TEXT NOT NULL,
  station_name TEXT NOT NULL DEFAULT '',
  institution_name TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  last_echo_at TEXT,
  last_echo_status TEXT NOT NULL DEFAULT 'UNKNOWN'
);
CREATE TABLE IF NOT EXISTS destinations (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  ae_title TEXT NOT NULL,
  host TEXT NOT NULL,
  port INTEGER NOT NULL,
  tls_mode TEXT NOT NULL DEFAULT 'disabled',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS routing_rules (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  source_ae TEXT NOT NULL DEFAULT '',
  modality TEXT NOT NULL DEFAULT '',
  station_name TEXT NOT NULL DEFAULT '',
  destination_id INTEGER NOT NULL REFERENCES destinations(id),
  priority INTEGER NOT NULL DEFAULT 100,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS worklist (
  id INTEGER PRIMARY KEY,
  tenant_ref TEXT NOT NULL DEFAULT '',
  patient_id TEXT NOT NULL,
  patient_name TEXT NOT NULL,
  accession_number TEXT NOT NULL,
  requested_procedure_id TEXT NOT NULL DEFAULT '',
  scheduled_station_ae_title TEXT NOT NULL,
  scheduled_station_name TEXT NOT NULL DEFAULT '',
  scheduled_start_date TEXT NOT NULL,
  scheduled_start_time TEXT NOT NULL DEFAULT '',
  modality TEXT NOT NULL,
  procedure_description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'SCHEDULED',
  cloud_cursor TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(accession_number, scheduled_station_ae_title)
);
CREATE TABLE IF NOT EXISTS studies (
  study_instance_uid TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  accession_number TEXT NOT NULL DEFAULT '',
  modality TEXT NOT NULL DEFAULT '',
  institution_name TEXT NOT NULL DEFAULT '',
  source_ae TEXT NOT NULL,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS series (
  series_instance_uid TEXT PRIMARY KEY,
  study_instance_uid TEXT NOT NULL REFERENCES studies(study_instance_uid),
  modality TEXT NOT NULL,
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dicom_instances (
  sop_instance_uid TEXT PRIMARY KEY,
  series_instance_uid TEXT NOT NULL REFERENCES series(series_instance_uid),
  study_instance_uid TEXT NOT NULL REFERENCES studies(study_instance_uid),
  sop_class_uid TEXT NOT NULL,
  modality TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  spool_path TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('RECEIVED','QUEUED','SENDING','SENT','FAILED','QUARANTINED')),
  received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sent_at TEXT,
  UNIQUE(sha256)
);
CREATE TABLE IF NOT EXISTS queue (
  id INTEGER PRIMARY KEY,
  sop_instance_uid TEXT NOT NULL UNIQUE REFERENCES dicom_instances(sop_instance_uid),
  destination_id INTEGER REFERENCES destinations(id),
  status TEXT NOT NULL CHECK(status IN ('PENDING','LEASED','RETRY','SENT','FAILED','CANCELLED')),
  priority INTEGER NOT NULL DEFAULT 100,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  leased_until TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS queue_attempts (
  id INTEGER PRIMARY KEY,
  queue_id INTEGER NOT NULL REFERENCES queue(id),
  attempt_no INTEGER NOT NULL,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  status TEXT NOT NULL,
  dicom_status INTEGER,
  error_code TEXT,
  error_message TEXT
);
CREATE TABLE IF NOT EXISTS quarantine_items (
  id INTEGER PRIMARY KEY,
  spool_path TEXT NOT NULL,
  source_ae TEXT NOT NULL,
  source_ip TEXT NOT NULL,
  reason_code TEXT NOT NULL,
  reason_detail TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT,
  resolved_by TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY,
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actor TEXT NOT NULL,
  event_type TEXT NOT NULL,
  category TEXT NOT NULL,
  source_ae TEXT,
  source_ip TEXT,
  patient_id_masked TEXT,
  accession_masked TEXT,
  study_uid_hash TEXT,
  outcome TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS system_logs (
  id INTEGER PRIMARY KEY,
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  level TEXT NOT NULL,
  category TEXT NOT NULL,
  event TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_worklist_filters ON worklist(scheduled_start_date, modality, scheduled_station_ae_title, status);
CREATE INDEX IF NOT EXISTS idx_studies_patient_accession ON studies(patient_id, accession_number);
CREATE INDEX IF NOT EXISTS idx_series_study_modality ON series(study_instance_uid, modality);
CREATE INDEX IF NOT EXISTS idx_queue_dispatch ON queue(status, next_attempt_at, priority);
CREATE INDEX IF NOT EXISTS idx_audit_time_category ON audit_logs(occurred_at, category);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version < 1:
                conn.executescript(MIGRATION_001)
                conn.execute("PRAGMA user_version = 1")
                conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (1,))

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
