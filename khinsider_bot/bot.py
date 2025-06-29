import logging
from collections.abc import Iterator
from re import Match

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    Message,
    ReactionTypeEmoji,
)
from khinsider import (
    fetch_tracks,
    get_album,
    get_publisher_albums,
    get_track,
    KHINSIDER_URL_REGEX,
    parse_khinsider_url,
    search_albums,
)
from khinsider.cache import CacheManager
from khinsider.enums import AlbumTypes
from khinsider.files import setup_download
from magic_filter import RegexpMode

from .config import TELEGRAM_TOKEN
from .constants import LIST_PAGE_LENGTH, ROOT_DOWNLOADS_PATH
from .decorators import (
    react_after,
    react_before,
    react_on_error,
)
from .enums import Emoji
from .util import (
    format_search_results,
    get_list_select_keyboard,
    send_album_data,
    send_album_list,
    send_audio_track,
)

logger = logging.getLogger('khinsider_bot')

bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dispatcher = Dispatcher()


async def handle_track_url(message: Message, match: Match) -> None:
    message_text = match[0]

    album_slug, track_name = parse_khinsider_url(message_text)

    try:
        track = get_track(album_slug, track_name)

    except Exception:
        await message.answer("Couldn't get track :-(")
        raise

    with setup_download(ROOT_DOWNLOADS_PATH) as download_dir:
        await send_audio_track(message, track, download_dir)


async def handle_album_url(message: Message, match: Match) -> None:
    message_text = match[0]

    album_slug = message_text.rsplit('/', maxsplit=1)[-1]

    await send_album_data(
        message,
        album_slug,
    )


@dispatcher.callback_query(F.data.startswith('download_album://'))
async def handle_download_album_button(callback_query: CallbackQuery) -> None:
    message = callback_query.message

    # TODO: Maybe move checking to separate function
    if not isinstance(message, Message):
        callback_query.answer('Unknown error!')
        logger.error(f'Expected message, got {message}')
        return

    await message.edit_reply_markup(reply_markup=None)

    if not callback_query.data:
        callback_query.answer('Unknown error!')
        logger.error('Got empty callback_query.data')
        return

    *_, md5_hash = callback_query.data.partition('://')

    cache_manager = CacheManager.get_manager()
    if not (album_slug := cache_manager.get_cached_object(md5_hash)):
        await callback_query.answer('Download not available. Resend album url')
        return

    await callback_query.answer()
    await message.react([ReactionTypeEmoji(emoji=Emoji.EYES)])

    try:
        album = get_album(album_slug)
    except Exception:
        message.react([ReactionTypeEmoji(emoji=Emoji.SEE_NO_EVIL)])
        raise

    with setup_download(ROOT_DOWNLOADS_PATH) as download_dir:
        for track in fetch_tracks(*album.track_urls):
            await send_audio_track(message, track, download_dir)

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
        'They must be separated by spaces or newlines for this to work.\n'
        '\n'
        'To search for albums type /search [query] \n'
        'You can search for particular type of album by '
        'prefixing query with #[album_type] .\n'
        'e.g. "/search #gr touhou" will search for all touhou gamerips.\n'
        'Available album types:\n'
        '- #ost - Official soundtracks\n'
        '- #gr - Sound and music gamerips\n'
        '- #arr - Music arrangements\n'
        '- #rmx - Remixes\n'
        '- #com - Compilation albums\n'
        '- #sgl - Singles\n'
        '- #ins - Inspired albums [Inspired by]\n'
    )


@dispatcher.message(Command('search'))
async def handle_search_command(message: Message) -> None:
    if not message.text:
        logger.error('Empty message text!')
        message.answer('Unknown error!')
        return
    query = message.text.removeprefix('/search').strip()

    if not query:
        await message.answer('Search query is empty')
        return

    if query.startswith('#'):
        album_type_arg, query = query.split(maxsplit=1)

        album_type = {
            '#ost': AlbumTypes.SOUNDTRACKS,
            '#gr': AlbumTypes.GAMERIPS,
            '#arr': AlbumTypes.ARRANGEMENTS,
            '#rmx': AlbumTypes.REMIXES,
            '#com': AlbumTypes.COMPILATIONS,
            '#sgl': AlbumTypes.SINGLES,
            '#ins': AlbumTypes.INSPIRED_BY,
        }.get(album_type_arg, AlbumTypes.EMPTY)
    else:
        album_type = AlbumTypes.EMPTY

    search_results = search_albums(query, album_type=album_type)

    if not search_results:
        await message.answer('I found nothing :(')
        return

    cache_manager = CacheManager.get_manager()
    list_md5 = cache_manager.cache_object(search_results)

    await send_album_list(
        message,
        search_results[0:LIST_PAGE_LENGTH],
        list_md5,
        current_page_num=0,
        last_page_num=len(search_results) // LIST_PAGE_LENGTH,
    )


@dispatcher.message(Command('publisher'))
async def handle_publisher_command(message: Message) -> None:
    if not message.text:
        logger.error('Empty message text!')
        message.answer('Unknown error!')
        return

    query = message.text.removeprefix('/publisher').strip()

    if not query:
        await message.answer('Publisher name is required!')
        return

    search_results = get_publisher_albums(query)

    if not search_results:
        await message.answer(
            'Publisher has no albums or name is incorrect!\n'
            'Note: to find something publisher name must be exact match!'
        )
        return

    cache_manager = CacheManager.get_manager()
    hash_ = cache_manager.cache_object(search_results)

    await send_album_list(
        message,
        search_results[0:LIST_PAGE_LENGTH],
        hash_,
        current_page_num=0,
        last_page_num=len(search_results) // LIST_PAGE_LENGTH,
    )


@dispatcher.callback_query(F.data.startswith('page://'))
async def handle_switch_page(callback_query: CallbackQuery) -> None:
    message = callback_query.message

    if not isinstance(message, Message):
        logger.error(f'Expected message, got {message}')
        callback_query.answer('Unknown error!')
        return

    if not callback_query.data:
        logger.error('Got empty callback_query.data')
        callback_query.answer('Unknown error!')
        return

    list_md5, page_n = callback_query.data.removeprefix('page://').split(';')
    page_n = int(page_n)

    cache_manager = CacheManager.get_manager()
    if not (album_list := cache_manager.get_cached_object(list_md5)):
        await callback_query.answer(
            'Search results invalid! Please, re-send search query.'
        )
        await message.react([ReactionTypeEmoji(emoji=Emoji.SEE_NO_EVIL)])
        return

    album_slice = album_list[
        LIST_PAGE_LENGTH * page_n : LIST_PAGE_LENGTH * (page_n + 1)
    ]

    await callback_query.answer()
    await message.edit_text(
        format_search_results(
            album_slice,
            page_num=page_n,
        ),
        reply_markup=get_list_select_keyboard(
            list_md5,
            current_page_num=page_n,
            last_page_num=len(album_list) // LIST_PAGE_LENGTH,
            page_len=len(album_slice),
        ),
    )


@dispatcher.callback_query(F.data.startswith('select://'))
async def handle_select_album(callback_query: CallbackQuery) -> None:
    message = callback_query.message

    if not isinstance(message, Message):
        logger.error(f'Expected message, got {message}')
        callback_query.answer('Unknown error!')
        return

    if not callback_query.data:
        logger.error('Got empty callback_query.data')
        callback_query.answer('Unknown error!')
        return

    list_md5, album_n = callback_query.data.removeprefix(
        'select://',
    ).split(';')
    album_n = int(album_n)

    cache_manager = CacheManager.get_manager()
    if not (album_list := cache_manager.get_cached_object(list_md5)):
        await callback_query.answer(
            'Search results invalid! Please, re-send search query.'
        )
        await message.react([ReactionTypeEmoji(emoji=Emoji.SEE_NO_EVIL)])
        return

    album_slug = album_list[album_n].slug

    await callback_query.answer(album_slug)
    await send_album_data(
        message,
        album_slug,
    )


@dispatcher.callback_query(F.data == ('dummy'))
async def handle_dummy_data(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
