from pathlib import Path

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from app.config.models import ServiceSettings, validate_ae_title
from app.database.database import Database
from app.queue.quarantine import QuarantineStore
from app.queue.spool import SpoolStore
from app.validation.dataset import mask_identifier, validate_dataset


def valid_dataset() -> Dataset:
    ds = Dataset()
    ds.PatientID = "PATIENT-001"
    ds.PatientName = "TEST^PATIENT"
    ds.StudyInstanceUID = "1.2.826.0.1.3680043.8.498.1"
    ds.SeriesInstanceUID = "1.2.826.0.1.3680043.8.498.2"
    ds.SOPInstanceUID = "1.2.826.0.1.3680043.8.498.3"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.Modality = "CT"
    ds.StudyDate = "20260822"
    ds.InstitutionName = "TEST"
    return ds


def test_dataset_validation_accepts_required_attributes():
    assert validate_dataset(valid_dataset()).accepted


def test_dataset_validation_rejects_missing_required_attribute():
    ds = valid_dataset()
    del ds.PatientID
    result = validate_dataset(ds)
    assert not result.accepted
    assert "PatientID" in result.missing


def test_identifier_masking():
    assert mask_identifier("12345678") == "12****78"
    assert mask_identifier("123") == "***"


def test_ae_validation():
    assert validate_ae_title("voxel_router") == "VOXEL_ROUTER"


def test_spool_is_idempotent(tmp_path: Path):
    db = Database(tmp_path / "router.sqlite3")
    db.initialize()
    spool = SpoolStore(tmp_path / "spool", db)
    first = spool.persist(b"DICOM_PART10_TEST", patient_id="P1", accession_number="A1", study_uid="1.2.3", series_uid="1.2.3.4", sop_uid="1.2.3.4.5", sop_class_uid="1.2.840.10008.5.1.4.1.1.2", modality="CT", institution_name="TEST", source_ae="CT01")
    second = spool.persist(b"DICOM_PART10_TEST", patient_id="P1", accession_number="A1", study_uid="1.2.3", series_uid="1.2.3.4", sop_uid="1.2.3.4.5", sop_class_uid="1.2.840.10008.5.1.4.1.1.2", modality="CT", institution_name="TEST", source_ae="CT01")
    assert not first.duplicate
    assert second.duplicate
    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0] == 1


def test_quarantine_persists_raw_dataset_and_reason(tmp_path: Path):
    db = Database(tmp_path / "router.sqlite3")
    db.initialize()
    quarantine = QuarantineStore(tmp_path / "quarantine", db)
    path = quarantine.persist(b"INVALID_DICOM", source_ae="CT01", source_ip="10.0.0.10", reason_code="MISSING_REQUIRED_DICOM_ATTRIBUTES", reason_detail="PatientID")
    assert path.exists()
    with db.connection() as conn:
        row = conn.execute("SELECT reason_code FROM quarantine_items").fetchone()
    assert row["reason_code"] == "MISSING_REQUIRED_DICOM_ATTRIBUTES"
