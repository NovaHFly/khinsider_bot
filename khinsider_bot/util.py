from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from random import randint
from shutil import rmtree
from time import sleep

from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from khinsider import Album, AudioTrack, download_track_file

from .constants import ROOT_DOWNLOADS_PATH


@contextmanager
def setup_download(existing_downloads: dict | None = None) -> Iterator[Path]:
    """Setup download path and remove it when done."""
    if existing_downloads is None:
        existing_downloads = {}

    while (
        download_id := randint(1, 999999)
    ) and download_id in existing_downloads:
        pass

    download_dir = (ROOT_DOWNLOADS_PATH) / str(download_id)
    existing_downloads[download_id] = download_dir

    try:
        yield download_dir
    finally:
        rmtree(download_dir, ignore_errors=True)
        existing_downloads.pop(download_id, None)


def get_album_info(album: Album) -> str:
    return (
        f'{album.name}\n'
        f'Year: {album.year}\n'
        f'Type: {album.type}\n'
        f'Track count: {album.track_count}'
    )


def get_album_keyboard(download_hash: str) -> InlineKeyboardMarkup:
    download_button = InlineKeyboardButton(
        text='Download',
        callback_data=f'download_album://{download_hash}',
    )
    return InlineKeyboardMarkup(inline_keyboard=[[download_button]])


async def send_audio_track(
    message: Message,
    track: AudioTrack,
    download_dir: Path,
) -> None:
    async def _send_track(from_, raise_error: False):
        await message.chat.do(ChatAction.UPLOAD_DOCUMENT)
        sleep(0.5)
        await message.answer_audio(from_)
        sleep(0.1)

    try:
        with suppress(TelegramBadRequest):
            await _send_track(track.mp3_url)
            return
        await _send_track(
            BufferedInputFile.from_file(
                download_track_file(
                    track,
                    download_dir,
                )
            )
        )
    except Exception as e:
        await message.answer(f'Error for track {track.mp3_url}: {e}')
