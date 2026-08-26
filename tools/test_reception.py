"""Cliente sintético para validação técnica do Storage SCP do VOXEL Router.

Este utilitário não usa nem grava dados clínicos reais.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage, Verification


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Teste sintético C-ECHO/C-STORE para o VOXEL Router"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host do Storage SCP")
    parser.add_argument("--port", default=11112, type=int, help="Porta do Storage SCP")
    parser.add_argument("--called-ae", default="VOXEL_ROUTER", help="AE Title chamado")
    parser.add_argument("--calling-ae", default="VOXEL_TEST_SCU", help="AE Title chamador")
    return parser


def synthetic_dataset() -> Dataset:
    now = datetime.now(UTC)
    dataset = Dataset()
    dataset.PatientID = "SYNTHETIC-TEST"
    dataset.PatientName = "TEST^SYNTHETIC"
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.SOPInstanceUID = generate_uid()
    dataset.SOPClassUID = CTImageStorage
    dataset.Modality = "CT"
    dataset.StudyDate = now.strftime("%Y%m%d")
    dataset.StudyTime = now.strftime("%H%M%S")
    dataset.InstitutionName = "VOXEL_TEST"
    dataset.Rows = 1
    dataset.Columns = 1
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = 8
    dataset.BitsStored = 8
    dataset.HighBit = 7
    dataset.PixelRepresentation = 0
    dataset.PixelData = b"\x00"
    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.MediaStorageSOPClassUID = CTImageStorage
    dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return dataset


def status_code(status: object) -> int | None:
    return getattr(status, "Status", None)


def main() -> int:
    arguments = build_parser().parse_args()
    sender = AE(ae_title=arguments.calling_ae)
    sender.add_requested_context(Verification)
    sender.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
    association = sender.associate(arguments.host, arguments.port, ae_title=arguments.called_ae)
    if not association.is_established:
        print("ERRO: associação DICOM não estabelecida.", file=sys.stderr)
        return 2

    try:
        echo = association.send_c_echo()
        if status_code(echo) != 0x0000:
            print(f"ERRO: C-ECHO retornou {status_code(echo)!r}.", file=sys.stderr)
            return 3

        store = association.send_c_store(synthetic_dataset())
        if status_code(store) != 0x0000:
            print(f"ERRO: C-STORE retornou {status_code(store)!r}.", file=sys.stderr)
            return 4
    finally:
        association.release()

    print("RECEPCAO_DICOM_OK echo=0x0000 store=0x0000 dataset=synthetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
