from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command
from aiogram.types import Document, Message, PhotoSize

from src.config import get_settings
from src.file_loader import DownloadedFile, download_telegram_file
from src.gpt_client import GptClient
from src.rate_limit import InMemoryRateLimiter
from src.text_extractors import ExtractionError, PdfTooLongError, extract_text


TELEGRAM_MESSAGE_LIMIT = 4096
ANSWER_CHUNK_SIZE = 3900


@dataclass
class IncomingFile:
    file_id: str
    original_name: str
    mime_type: str | None
    size: int | None


settings = get_settings()
session = AiohttpSession(proxy=settings.telegram_proxy_url)
bot = Bot(token=settings.telegram_bot_token, session=session)
dp = Dispatcher()
gpt_client = GptClient(api_key=settings.openai_api_key, model=settings.openai_model)
rate_limiter = InMemoryRateLimiter(
    daily_limit=settings.user_daily_limit,
    min_seconds_between_requests=settings.user_min_seconds_between_requests,
)


@dp.message(Command("start", "help"))
async def handle_start(message: Message) -> None:
    await message.answer(
        "Отправьте фото, PDF или DOCX с заданием. "
        "Я распознаю текст, определю тип задания и верну ответ."
    )


@dp.message(F.photo | F.document)
async def handle_file(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    incoming_file = _get_incoming_file(message)
    if incoming_file is None:
        await message.answer("Отправьте фото, PDF или DOCX.")
        return

    if incoming_file.size is not None and incoming_file.size > settings.max_file_bytes:
        await message.answer(
            f"Файл слишком большой. Максимум: {settings.max_file_mb} МБ."
        )
        return

    limit_result = rate_limiter.check_and_increment(message.from_user.id)
    if not limit_result.allowed:
        await message.answer(limit_result.message or "Лимит запросов исчерпан.")
        return

    status_message = await message.answer("Файл получен. Извлекаю текст...")
    downloaded_file: DownloadedFile | None = None

    try:
        downloaded_file = await download_telegram_file(
            bot,
            file_id=incoming_file.file_id,
            original_name=incoming_file.original_name,
            mime_type=incoming_file.mime_type,
        )

        downloaded_size = downloaded_file.path.stat().st_size
        if downloaded_size > settings.max_file_bytes:
            await status_message.edit_text(
                f"Файл слишком большой. Максимум: {settings.max_file_mb} МБ."
            )
            return

        extracted_text = await extract_text(
            downloaded_file.path,
            mime_type=downloaded_file.mime_type,
            max_pdf_pages=settings.max_pdf_pages,
            vision_ocr=gpt_client.extract_text_from_image,
        )

        if not extracted_text.strip():
            await status_message.edit_text(
                "Не удалось извлечь текст. Попробуйте отправить более четкий файл."
            )
            return

        await status_message.edit_text("Текст распознан. Готовлю ответ...")
        answer = await gpt_client.answer_task(extracted_text)
        await status_message.delete()
        await send_long_message(message, answer)

    except PdfTooLongError as error:
        await status_message.edit_text(
            f"PDF слишком длинный: {error.pages} стр. Максимум: {error.limit}."
        )
    except ExtractionError as error:
        await status_message.edit_text(str(error))
    except Exception:
        logging.exception("Failed to process file")
        await status_message.edit_text(
            "Не получилось обработать файл. Попробуйте другой файл или повторите позже."
        )
    finally:
        if downloaded_file is not None:
            downloaded_file.cleanup()


@dp.message(F.text)
async def handle_text_question(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Напишите вопрос или отправьте фото, PDF или DOCX.")
        return

    limit_result = rate_limiter.check_and_increment(message.from_user.id)
    if not limit_result.allowed:
        await message.answer(limit_result.message or "Лимит запросов исчерпан.")
        return

    status_message = await message.answer("Готовлю ответ...")

    try:
        answer = await gpt_client.answer_task(text)
        await status_message.delete()
        await send_long_message(message, answer)
    except Exception:
        logging.exception("Failed to answer text question")
        await status_message.edit_text(
            "Не получилось подготовить ответ. Попробуйте повторить позже."
        )


@dp.message()
async def handle_other(message: Message) -> None:
    await message.answer("Напишите вопрос или отправьте фото, PDF или DOCX с заданием.")



def _get_incoming_file(message: Message) -> IncomingFile | None:
    if message.photo:
        photo: PhotoSize = message.photo[-1]
        return IncomingFile(
            file_id=photo.file_id,
            original_name=f"photo-{photo.file_unique_id}.jpg",
            mime_type="image/jpeg",
            size=photo.file_size,
        )

    document: Document | None = message.document
    if document is None:
        return None

    return IncomingFile(
        file_id=document.file_id,
        original_name=document.file_name or f"document-{document.file_unique_id}",
        mime_type=document.mime_type,
        size=document.file_size,
    )


async def send_long_message(message: Message, text: str) -> None:
    stripped = text.strip()
    if not stripped:
        await message.answer("GPT не вернул ответ. Попробуйте повторить запрос.")
        return

    for start in range(0, len(stripped), ANSWER_CHUNK_SIZE):
        chunk = stripped[start : start + ANSWER_CHUNK_SIZE]
        await message.answer(chunk)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        await dp.start_polling(bot)
    except TelegramNetworkError:
        logging.exception(
            "Cannot connect to Telegram API. Check internet/VPN/proxy access to api.telegram.org. "
            "For local proxy set TELEGRAM_PROXY_URL in .env."
        )
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
