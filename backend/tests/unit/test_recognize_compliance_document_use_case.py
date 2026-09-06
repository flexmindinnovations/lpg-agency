"""Unit tests for RecognizeComplianceDocumentUseCase — doc_kind routing and
the missing-blob path. Field extraction itself is covered by
test_compliance_document_parser.py."""

from __future__ import annotations

import pytest

from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import DocumentOcrResult
from lpg.application.delivery.compliance_use_cases import (
    RecognizeComplianceDocumentCommand,
    RecognizeComplianceDocumentUseCase,
)

_DL_TEXT = "DRIVING LICENCE\nDL No : MH12 20110012345\nValid Till : 13-08-2028"
_RC_TEXT = "CERTIFICATE OF REGISTRATION\nRegn No : MH 12 AB 1234\nRegn Valid Upto : 04-06-2036"


class _FakeStorage:
    """Just the one `FileStorage` method the use case calls."""

    def __init__(self, content: bytes | None) -> None:
        self._content = content

    async def download(self, key: str) -> bytes | None:
        del key
        return self._content


class _FakeOcr:
    def __init__(self, text: str) -> None:
        self._text = text

    async def recognize(self, image_bytes: bytes) -> DocumentOcrResult:
        del image_bytes
        return DocumentOcrResult(text=self._text, confidence=0.9)


def _use_case(storage: _FakeStorage, ocr: _FakeOcr) -> RecognizeComplianceDocumentUseCase:
    return RecognizeComplianceDocumentUseCase(storage, ocr)  # type: ignore[arg-type]


async def test_routes_to_the_driving_licence_parser() -> None:
    result = await _use_case(_FakeStorage(b"img"), _FakeOcr(_DL_TEXT)).execute(
        RecognizeComplianceDocumentCommand(blob_ref="k", doc_kind="driving_licence")
    )
    assert result.doc_kind == "driving_licence"
    assert result.document_number == "MH1220110012345"
    assert result.valid_till is not None
    assert result.registration_number is None


async def test_routes_to_the_rc_parser() -> None:
    result = await _use_case(_FakeStorage(b"img"), _FakeOcr(_RC_TEXT)).execute(
        RecognizeComplianceDocumentCommand(blob_ref="k", doc_kind="vehicle_rc")
    )
    assert result.doc_kind == "vehicle_rc"
    assert result.registration_number == "MH12AB1234"
    assert result.document_number == "MH12AB1234"


async def test_missing_blob_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _use_case(_FakeStorage(None), _FakeOcr(_DL_TEXT)).execute(
            RecognizeComplianceDocumentCommand(blob_ref="gone", doc_kind="driving_licence")
        )


async def test_unknown_doc_kind_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _use_case(_FakeStorage(b"img"), _FakeOcr(_DL_TEXT)).execute(
            RecognizeComplianceDocumentCommand(blob_ref="k", doc_kind="passport")
        )
