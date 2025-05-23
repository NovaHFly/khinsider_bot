from os import getenv
from pathlib import Path
from re import Match
from time import sleep

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from khinsider import get_album_data, get_track_data, KHINSIDER_URL_REGEX

from .core import downloader
from .decorators import (
    set_error_reaction,
    set_noticed_reaction,
    set_success_reaction,
)
from .enums import ReactionEmoji
from .util import setup_download

bot = Bot(
    token=getenv('TELEGRAM_TOKEN'),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dispatcher = Dispatcher()


async def safe_reply_audio(
    message: Message,
    audio_location: Path | str,
) -> Message | None:
    """Send audio safely, retrying on telegram network error."""
    while True:
        try:
            await message.chat.do(ChatAction.UPLOAD_DOCUMENT)
            sleep(1)
            return await message.answer_audio(audio_location)
        except TelegramNetworkError:
            continue


async def handle_track_url(message: Message) -> None:
    # Read only first line
    cleaned_text = message.text.splitlines()[0]
    try:
        track_url = get_track_data(cleaned_text).mp3_url

    except Exception:
        await message.answer("Couldn't get track :-(")
        raise

    if await safe_reply_audio(message, track_url):
        return

    with setup_download(_pending_downloads) as download_dir:
        (track_path,) = downloader.download(
            cleaned_text,
            download_path=download_dir,
        )
        await safe_reply_audio(message, track_path)


async def handle_album_url(message: Message) -> None:
    cleaned_text = message.text.splitlines()[0]

    try:
        album = get_album_data(cleaned_text)
    except Exception:
        await message.answer("Couldn't get album data :-(")
        raise

    await message.answer_photo(
        album.thumbnail_urls[0],
        caption=(
            f'{album.name}\n'
            f'Year: {album.year}\n'
            f'Type: {album.type}\n'
            f'Track count: {album.track_count}'
        ),
    )
    with setup_download(_pending_downloads) as download_dir:
        for track in downloader.fetch_tracks(album.track_urls):
            if await safe_reply_audio(message, track.mp3_url):
                continue

            (track_path,) = downloader.download(track.page_url, download_dir)
            await safe_reply_audio(message, track_path)
            track_path.unlink(missing_ok=True)


@dispatcher.message(F.text.regexp(KHINSIDER_URL_REGEX).as_('match'))
@set_noticed_reaction(reaction=ReactionEmoji.EYES)
@set_error_reaction(reaction=ReactionEmoji.SEE_NO_EVIL)
@set_success_reaction(reaction=ReactionEmoji.THUMBS_UP)
async def handle_khinsider_url(message: Message, match: Match) -> None:
    if match[2]:
        await handle_track_url(message)
        return

    await handle_album_url(message)


@dispatcher.message(CommandStart())
async def handle_start_command(message: Message) -> None:
    await message.answer(
        'Hello! I am khinsider bot.'
        '\nI can download albums and tracks from downloads.khinsider.com.'
        '\nJust send me the album or track url.',
    )


@dispatcher.message(Command('help'))
async def handle_help_command(message: Message) -> None:
    await message.answer(
        'To download audio from downloads.khinsider.com just send me url.\n'
        '\n'
        '- Send album url to download whole album.\n'
        'https://downloads.khinsider.com/game-soundtracks'
        '/album/persona-3-reload-original-soundtrack-2024\n'
        '\n'
        '- Send track url to download specific track.\n'
        'https://downloads.khinsider.com/game-soundtracks'
        '/album/persona-3-reload-original-soundtrack-2024'
        '/2-20.%2520Battle%2520Hymn%2520of%2520the%2520Soul%2520%2528P3R%2520ver.%2529.mp3\n',
    )


_pending_downloads = {}
