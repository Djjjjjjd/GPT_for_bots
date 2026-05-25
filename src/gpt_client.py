from __future__ import annotations

import base64
import re
from pathlib import Path

from openai import AsyncOpenAI

from src.prompts import SYSTEM_PROMPT, VISION_OCR_PROMPT


class GptClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def answer_task(self, extracted_text: str) -> str:
        response = await self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_PROMPT,
            input=(
                "Text extracted from the user's file:\n\n"
                f"{extracted_text.strip()}"
            ),
        )
        return strip_markdown(response.output_text)

    async def answer_task_with_image(self, image_path: Path) -> str:
        """Send a single image directly to GPT Vision and get the task answer."""
        return await self.answer_task_with_images([image_path])

    async def answer_task_with_images(self, image_paths: list[Path]) -> str:
        """Send multiple images (e.g. scanned PDF pages) to GPT Vision and get the task answer."""
        content = _build_image_content(image_paths)
        response = await self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": content}],
        )
        return strip_markdown(response.output_text)

    async def extract_text_from_image(self, image_path: Path) -> str:
        image_bytes = image_path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("ascii")
        mime_type = _guess_image_mime_type(image_path)

        response = await self._client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": VISION_OCR_PROMPT},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{encoded}",
                        },
                    ],
                }
            ],
        )
        return response.output_text.strip()


def _build_image_content(image_paths: list[Path]) -> list[dict]:
    content = []
    for image_path in image_paths:
        image_bytes = image_path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("ascii")
        mime_type = _guess_image_mime_type(image_path)
        content.append({
            "type": "input_image",
            "image_url": f"data:{mime_type};base64,{encoded}",
        })
    return content


def _guess_image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def strip_markdown(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"```(?:\w+)?\n?(.*?)```", r"\1", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"(\*\*|__)(.*?)\1", r"\2", cleaned)
    cleaned = re.sub(r"(\*|_)(.*?)\1", r"\2", cleaned)
    cleaned = re.sub(r"^\s{0,3}>\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
