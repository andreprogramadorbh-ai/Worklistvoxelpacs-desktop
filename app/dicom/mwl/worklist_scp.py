from __future__ import annotations

from datetime import datetime
from typing import Any, Iterator

from pydicom.dataset import Dataset
from pynetdicom import AE, evt
from pynetdicom.sop_class import ModalityWorklistInformationFind, Verification

from app.config.models import ServiceSettings
from app.database.database import Database


class WorklistScp:
    def __init__(self, settings: ServiceSettings, database: Database) -> None:
        self.settings = settings
        self.database = database
        self._server: Any | None = None

    def start(self) -> None:
        ae = AE(ae_title=self.settings.router_ae_title)
        ae.add_supported_context(Verification)
        ae.add_supported_context(ModalityWorklistInformationFind)
        self._server = ae.start_server(
            (self.settings.dicom_host, self.settings.mwl_port),
            block=False,
            evt_handlers=[(evt.EVT_C_ECHO, lambda _: 0x0000), (evt.EVT_C_FIND, self._handle_find)],
        )

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def _handle_find(self, event: Any) -> Iterator[tuple[int, Dataset | None]]:
        identifier = event.identifier
        sps = getattr(identifier, "ScheduledProcedureStepSequence", [Dataset()])[0]
        station = str(getattr(sps, "ScheduledStationAETitle", "")).strip()
        modality = str(getattr(sps, "Modality", "")).strip()
        date_filter = str(getattr(sps, "ScheduledProcedureStepStartDate", "")).strip()
        patient_id = str(getattr(identifier, "PatientID", "")).strip()
        patient_name = str(getattr(identifier, "PatientName", "")).strip().replace("*", "%")

        clauses = ["status='SCHEDULED'"]
        values: list[str] = []
        if station:
            clauses.append("scheduled_station_ae_title=?")
            values.append(station)
        if modality:
            clauses.append("modality=?")
            values.append(modality)
        if patient_id:
            clauses.append("patient_id=?")
            values.append(patient_id)
        if patient_name and patient_name != "%":
            clauses.append("patient_name LIKE ?")
            values.append(patient_name)
        if len(date_filter) == 8:
            clauses.append("scheduled_start_date=?")
            values.append(date_filter)
        query = "SELECT * FROM worklist WHERE " + " AND ".join(clauses) + " ORDER BY scheduled_start_date,scheduled_start_time LIMIT 500"
        with self.database.connection() as conn:
            rows = conn.execute(query, values).fetchall()
        for row in rows:
            result = Dataset()
            result.PatientName = row["patient_name"]
            result.PatientID = row["patient_id"]
            result.AccessionNumber = row["accession_number"]
            result.RequestedProcedureID = row["requested_procedure_id"]
            result.RequestedProcedureDescription = row["procedure_description"]
            step = Dataset()
            step.ScheduledStationAETitle = row["scheduled_station_ae_title"]
            step.ScheduledStationName = row["scheduled_station_name"]
            step.ScheduledProcedureStepStartDate = row["scheduled_start_date"]
            step.ScheduledProcedureStepStartTime = row["scheduled_start_time"]
            step.Modality = row["modality"]
            step.ScheduledProcedureStepDescription = row["procedure_description"]
            step.ScheduledProcedureStepID = row["accession_number"]
            result.ScheduledProcedureStepSequence = [step]
            yield 0xFF00, result
        yield 0x0000, None
