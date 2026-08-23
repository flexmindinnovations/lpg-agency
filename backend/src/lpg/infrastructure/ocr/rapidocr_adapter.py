"""`DocumentOcrPort` backed by RapidOCR (PP-OCRv6 via ONNX Runtime, CPU).

The backend "second pass" for KYC document auto-fill — see
`application/customer/ports.py::DocumentOcrPort` and
`RecognizeKycDocumentUseCase`'s docstrings for why this runs server-side at
all given the frontend already does its own OCR pass in-browser.

Both detection and recognition use PP-OCRv6's small model tier. Recognition
is the actual bottleneck on a real ID photo, not detection: profiling showed
detection taking ~1-2s regardless of model size, while recognition runs once
per *detected text line* — a real Aadhaar/PAN card has bilingual duplicate
text, an address block, and boilerplate legal paragraphs, easily producing
50-100+ detected lines, and at the medium tier recognition alone cost
roughly ~0.5s/line (a dense card could take 30-45s end to end). Dropping
recognition to the small tier measured ~5x faster (~18s -> ~3s recognizing
32 lines) with *no measurable accuracy loss* on the fields this parser
actually reads (name, DOB, document number) — tested against both clean
text and text degraded with blur/noise/rotation/JPEG compression to
approximate a real phone photo; confidence scores and extracted values were
effectively identical between tiers in both cases. PP-OCR's model tiers
mainly trade off robustness on very degraded/tiny text, which matters far
less here than the *volume* of boilerplate text this pipeline has to churn
through on every upload. `Rec.lang_type=EN` is set because the fields this
wizard extracts are always printed in English on Aadhaar/PAN cards; the
Hindi lines are a duplicate of the same information, not additional data.

Model weights (~130 MB combined) are not vendored in this repo — RapidOCR
downloads them from its own ModelScope-hosted release on first use and
caches them on local disk afterward, the same "generic engine asset, not
customer data, cached after first load" tradeoff already accepted for the
frontend's OCR models and Tesseract's trained-data files before that.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lpg.application.customer.ports import DocumentOcrResult
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from rapidocr import RapidOCR

_logger = get_logger(__name__)

_engine: RapidOCR | None = None
_engine_lock = asyncio.Lock()


async def _get_engine() -> RapidOCR:
    """Lazily builds the RapidOCR engine once per process and reuses it.

    Construction loads ~130 MB of ONNX models into memory (and, on a cold
    cache, downloads them first) — expensive enough that it must happen at
    most once, not per request. Lazy rather than eager-at-startup: this is
    an occasional "second pass" feature, not a critical-path dependency
    like the database or Redis, so there is no reason to slow down every
    server boot (or `--reload` restart) for a feature a given session may
    never exercise.
    """
    global _engine
    if _engine is not None:
        return _engine

    async with _engine_lock:
        if _engine is None:
            _engine = await asyncio.to_thread(_build_engine)
    return _engine


def _build_engine() -> RapidOCR:
    from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

    _logger.info("kyc_ocr_engine_loading")
    engine = RapidOCR(
        params={
            "Det.model_type": ModelType.SMALL,
            "Det.ocr_version": OCRVersion.PPOCRV6,
            "Rec.lang_type": LangRec.EN,
            "Rec.model_type": ModelType.SMALL,
            "Rec.ocr_version": OCRVersion.PPOCRV6,
        }
    )
    _logger.info("kyc_ocr_engine_loaded")
    return engine


class RapidOcrDocumentAdapter:
    async def recognize(self, image_bytes: bytes) -> DocumentOcrResult:
        from rapidocr.utils.output import RapidOCROutput

        engine = await _get_engine()
        result = await asyncio.to_thread(engine, image_bytes)

        if not isinstance(result, RapidOCROutput) or not result.txts or not result.scores:
            _logger.info("kyc_ocr_recognized", line_count=0)
            return DocumentOcrResult(text="", confidence=0.0)

        _logger.info("kyc_ocr_recognized", line_count=len(result.txts))
        text = "\n".join(result.txts)
        confidence = sum(result.scores) / len(result.scores)
        return DocumentOcrResult(text=text, confidence=confidence)
