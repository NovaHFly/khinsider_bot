from collections.abc import Iterator
from hashlib import md5
from logging import getLogger
from os import getenv
from pathlib import Path
from re import Match
from time import sleep

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReactionTypeEmoji,
    URLInputFile,
)
from khinsider import (
    get_album,
    get_track,
    KHINSIDER_BASE_URL,
    KHINSIDER_URL_REGEX,
)
from magic_filter import RegexpMode

from .constants import ROOT_DOWNLOADS_PATH
from .core import downloader
from .decorators import (
    react_after,
    react_before,
    react_on_error,
)
from .enums import Emoji

logger = getLogger('khinsider_bot')

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


async def handle_track_url(message: Message, match: Match) -> None:
    message_text = match[0]

    try:
        track_url = get_track(message_text).mp3_url

    except Exception:
        await message.answer("Couldn't get track :-(")
        raise

    if await safe_reply_audio(message, track_url):
        return


async def handle_album_url(message: Message, match: Match) -> None:
    message_text = match[0]

    try:
        album = get_album(message_text)
    except Exception:
        await message.answer("Couldn't get album data :-(")
        raise

    md5_hash = md5(album.slug.encode()).hexdigest()

    with (ROOT_DOWNLOADS_PATH / md5_hash).open('w') as f:
        f.write(album.slug)

    if album.thumbnail_urls:
        await message.reply_photo(URLInputFile(album.thumbnail_urls[0]))
    await message.reply(
        f'{album.name}\n'
        f'Year: {album.year}\n'
        f'Type: {album.type}\n'
        f'Track count: {album.track_count}',
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text='Download',
                        callback_data=f'download_album://{md5_hash}',
                    ),
                ],
            ]
        ),
    )


@dispatcher.callback_query(F.data.startswith('download_album://'))
async def handle_download_album_button(callback_query: CallbackQuery) -> None:
    message = callback_query.message
    await message.edit_reply_markup(reply_markup=None)

    *_, md5_hash = callback_query.data.partition('://')

    slug_file_path = ROOT_DOWNLOADS_PATH / md5_hash
    if not slug_file_path.exists():
        await callback_query.answer(
            'Download unavailable! Please, resend album url!'
        )
        await message.react(
            reaction=[ReactionTypeEmoji(emoji=Emoji.THUMBS_DOWN)]
        )
        return

    await message.react(reaction=[ReactionTypeEmoji(emoji=Emoji.EYES)])

    with slug_file_path.open() as f:
        album_slug = f.read().strip()
    slug_file_path.unlink(missing_ok=True)

    await callback_query.answer()

    album = get_album(
        f'{KHINSIDER_BASE_URL}/game-soundtracks/album/{album_slug}'
    )

    for track in downloader.fetch_tracks(album.track_urls):
        if await safe_reply_audio(message, track.mp3_url):
            continue
        await message.answer(f'Error for track {track.mp3_url}')

    await message.react(reaction=[ReactionTypeEmoji(emoji=Emoji.THUMBS_UP)])


@dispatcher.message(
    F.text.regexp(KHINSIDER_URL_REGEX)
    & F.text.regexp(
        KHINSIDER_URL_REGEX,
        mode=RegexpMode.FINDITER,
    ).as_('match_iter')
)
@react_before(emoji=Emoji.EYES)
@react_on_error(emoji=Emoji.SEE_NO_EVIL)
@react_after(emoji=Emoji.THUMBS_UP)
async def handle_khinsider_url(
    message: Message, match_iter: Iterator[Match]
) -> None:
    for match in match_iter:
        if match[2]:
            await handle_track_url(message, match)
            continue

        await handle_album_url(message, match)


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
        '/2-20.%2520Battle%2520Hymn%2520of%2520the%2520Soul%2520%2528P3R%2520ver.%2529.mp3\n'
        '\n'
        'You can also send multiple valid urls in the same message.\n'
        'They must be separated by spaces or newlines for this to work.'
    )
