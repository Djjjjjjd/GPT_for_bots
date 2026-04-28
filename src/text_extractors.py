from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from pdf2image import convert_from_path
from PIL import Image
from pypdf import PdfReader
import pytesseract


VisionOcr = Callable[[Path], Awaitable[str]]


class ExtractionError(Exception):
    """Raised when text cannot be extracted from a supported file."""


class PdfTooLongError(ExtractionError):
    def __init__(self, pages: int, limit: int) -> None:
        super().__init__(f"PDF содержит {pages} стр., максимум: {limit}.")
        self.pages = pages
        self.limit = limit


async def extract_text(
    path: Path,
    *,
    mime_type: str | None,
    max_pdf_pages: int,
    vision_ocr: VisionOcr,
) -> str:
    suffix = path.suffix.lower()

    if _is_image(suffix, mime_type):
        return await extract_image_text(path, vision_ocr)

    if suffix == ".pdf" or mime_type == "application/pdf":
        return await extract_pdf_text(path, max_pdf_pages=max_pdf_pages, vision_ocr=vision_ocr)

    if suffix == ".docx":
        return extract_docx_text(path)

    if suffix == ".doc":
        raise ExtractionError("Формат .doc пока не поддерживается. Отправьте .docx или PDF.")

    raise ExtractionError("Поддерживаются фото, PDF и DOCX.")


async def extract_image_text(path: Path, vision_ocr: VisionOcr) -> str:
    local_text = await asyncio.to_thread(_tesseract_image_to_string, path)
    if _has_enough_text(local_text):
        return local_text.strip()

    fallback_text = await vision_ocr(path)
    return fallback_text.strip()


async def extract_pdf_text(path: Path, *, max_pdf_pages: int, vision_ocr: VisionOcr) -> str:
    reader = PdfReader(str(path))
    page_count = len(reader.pages)

    if page_count > max_pdf_pages:
        raise PdfTooLongError(page_count, max_pdf_pages)

    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(page_text.strip())

    text = "\n\n".join(text_parts)
    if _has_enough_text(text):
        return text

    return await _ocr_pdf_pages(path, max_pdf_pages=max_pdf_pages, vision_ocr=vision_ocr)


def extract_docx_text(path: Path) -> str:
    document = Document(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    text = "\n".join(paragraph for paragraph in paragraphs if paragraph)

    if not _has_enough_text(text):
        raise ExtractionError("Не удалось найти текст в DOCX.")

    return text


async def _ocr_pdf_pages(path: Path, *, max_pdf_pages: int, vision_ocr: VisionOcr) -> str:
    with TemporaryDirectory(prefix="pdf-pages-") as temp_dir:
        pages = await asyncio.to_thread(
            convert_from_path,
            str(path),
            first_page=1,
            last_page=max_pdf_pages,
            output_folder=temp_dir,
            fmt="png",
        )

        page_texts: list[str] = []
        for index, image in enumerate(pages, start=1):
            image_path = Path(temp_dir) / f"page-{index}.png"
            image.save(image_path, "PNG")

            local_text = await asyncio.to_thread(pytesseract.image_to_string, image)
            if _has_enough_text(local_text):
                page_texts.append(local_text.strip())
                continue

            fallback_text = await vision_ocr(image_path)
            if fallback_text.strip():
                page_texts.append(fallback_text.strip())

    text = "\n\n".join(page_texts).strip()
    if not _has_enough_text(text):
        raise ExtractionError("Не удалось распознать текст в PDF.")

    return text


def _tesseract_image_to_string(path: Path) -> str:
    with Image.open(path) as image:
        return pytesseract.image_to_string(image)


def _has_enough_text(text: str) -> bool:
    letters = [char for char in text if char.isalnum()]
    return len(letters) >= 20


def _is_image(suffix: str, mime_type: str | None) -> bool:
    return suffix in {".jpg", ".jpeg", ".png", ".webp"} or (
        mime_type is not None and mime_type.startswith("image/")
    )
