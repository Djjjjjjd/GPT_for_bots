from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import Bot


@dataclass
class DownloadedFile:
    path: Path
    original_name: str
    mime_type: str | None
    temporary_directory: TemporaryDirectory[str]

    def cleanup(self) -> None:
        self.temporary_directory.cleanup()


async def download_telegram_file(
    bot: Bot,
    file_id: str,
    original_name: str,
    mime_type: str | None = None,
) -> DownloadedFile:
    tg_file = await bot.get_file(file_id)
    temp_dir = TemporaryDirectory(prefix="telegram-file-")
    target_path = Path(temp_dir.name) / safe_filename(original_name)

    await bot.download_file(tg_file.file_path, destination=target_path)
    return DownloadedFile(
        path=target_path,
        original_name=original_name,
        mime_type=mime_type,
        temporary_directory=temp_dir,
    )


def safe_filename(name: str) -> str:
    cleaned = "".join(char for char in name if char.isalnum() or char in "._- ")
    cleaned = cleaned.strip(" .")
    return cleaned or "telegram-file"
