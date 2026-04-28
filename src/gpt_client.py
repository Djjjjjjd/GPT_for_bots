from __future__ import annotations

import base64
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
        return response.output_text.strip()

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


def _guess_image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"
