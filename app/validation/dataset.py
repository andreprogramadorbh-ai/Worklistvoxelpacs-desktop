from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

REQUIRED_ATTRIBUTES = (
    "PatientID",
    "PatientName",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "SOPInstanceUID",
    "SOPClassUID",
    "Modality",
    "StudyDate",
    "InstitutionName",
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    accepted: bool
    missing: tuple[str, ...] = ()
    reason_code: str = "OK"


def validate_dataset(dataset: Any) -> ValidationResult:
    missing = tuple(name for name in REQUIRED_ATTRIBUTES if not str(getattr(dataset, name, "")).strip())
    if missing:
        return ValidationResult(False, missing, "MISSING_REQUIRED_DICOM_ATTRIBUTES")
    if len(str(dataset.SOPInstanceUID)) > 64 or len(str(dataset.StudyInstanceUID)) > 64:
        return ValidationResult(False, (), "INVALID_UID_LENGTH")
    return ValidationResult(True)


def mask_identifier(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def uid_fingerprint(uid: str) -> str:
    return sha256(uid.encode("utf-8")).hexdigest()[:20]
