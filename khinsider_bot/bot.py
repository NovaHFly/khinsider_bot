import logging
from collections.abc import Iterator
from hashlib import md5
from os import getenv
from re import Match
from time import sleep

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    Message,
    ReactionTypeEmoji,
    URLInputFile,
)
from khinsider import (
    get_album,
    get_track,
    KHINSIDER_URL_REGEX,
)
from magic_filter import RegexpMode

from .core import downloader
from .decorators import (
    react_after,
    react_before,
    react_on_error,
)
from .enums import Emoji
from .util import get_album_info, get_album_keyboard, setup_download

logger = logging.getLogger('khinsider_bot')

bot = Bot(
    token=getenv('TELEGRAM_TOKEN'),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dispatcher = Dispatcher()


async def handle_track_url(message: Message, match: Match) -> None:
    message_text = match[0]

    _, album_slug, track_name = message_text.rsplit('/', maxsplit=2)

    try:
        track = get_track(track_name, album_slug)

    except Exception:
        await message.answer("Couldn't get track :-(")
        raise

    with setup_download(_download_dirs) as download_dir:
        try:
            await message.chat.do(ChatAction.UPLOAD_DOCUMENT)
            sleep(1)
            await message.answer_audio(track.mp3_url)
        except TelegramBadRequest:
            tasks = downloader.download(track.page_url, download_dir)
            (path,) = tasks
            await message.answer_audio(BufferedInputFile.from_file(path))
        except Exception as e:
            await message.answer(f'Error for track {track.mp3_url}: {e}')


async def handle_album_url(message: Message, match: Match) -> None:
    message_text = match[0]

    try:
        album = get_album(message_text.rsplit('/', maxsplit=1)[-1])
    except Exception:
        await message.answer("Couldn't get album data :-(")
        raise

    md5_hash = md5(album.slug.encode()).hexdigest()

    _pending_downloads[md5_hash] = album.slug

    if album.thumbnail_urls:
        await message.reply_photo(URLInputFile(album.thumbnail_urls[0]))

    await message.reply(
        text=get_album_info(album),
        reply_markup=get_album_keyboard(md5_hash),
    )


@dispatcher.callback_query(F.data.startswith('download_album://'))
async def handle_download_album_button(callback_query: CallbackQuery) -> None:
    message = callback_query.message

    await message.edit_reply_markup(reply_markup=None)

    *_, md5_hash = callback_query.data.partition('://')

    try:
        album_slug = _pending_downloads.pop(md5_hash)
    except KeyError:
        await callback_query.answer('Download not available. Resend album url')
        return

    await callback_query.answer()
    await message.react([ReactionTypeEmoji(emoji=Emoji.EYES)])

    try:
        album = get_album(album_slug)
    except Exception:
        message.react([ReactionTypeEmoji(emoji=Emoji.SEE_NO_EVIL)])
        raise

    for track_url in album.track_urls:
        track = get_track(*track_url.rsplit('/', maxsplit=2)[:0:-1])
        with setup_download(_download_dirs) as download_dir:
            try:
                await message.chat.do(ChatAction.UPLOAD_DOCUMENT)
                sleep(1)
                await message.answer_audio(track.mp3_url)
            except TelegramBadRequest:
                tasks = downloader.download(track.page_url, download_dir)
                (path,) = tasks
                await message.answer_audio(BufferedInputFile.from_file(path))
            except Exception as e:
                await message.answer(f'Error for track {track.mp3_url}: {e}')

    await message.react([ReactionTypeEmoji(emoji=Emoji.THUMBS_UP)])


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


_pending_downloads = {}
_download_dirs = {}
