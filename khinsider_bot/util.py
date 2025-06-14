from collections.abc import Collection, Iterator
from contextlib import contextmanager, suppress
from hashlib import md5
from pathlib import Path
from random import randint
from shutil import rmtree
from time import sleep

from aiogram import html
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    URLInputFile,
)
from khinsider import (
    Album,
    AlbumShort,
    AudioTrack,
    download_track_file,
    get_album,
)

from .constants import LIST_PAGE_LENGTH, ROOT_DOWNLOADS_PATH


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


def batch_collection(
    collection: Collection,
    batch_size: int = 5,
) -> list[list]:
    return [
        collection[batch_size * n : batch_size * (n + 1)]
        for n in range(len(collection) // batch_size + 1)
    ]


def format_album_info(album: Album) -> str:
    return (
        f'{album.name}\n'
        f'Year: {album.year}\n'
        f'Type: {album.type}\n'
        f'Track count: {album.track_count}'
    )


def format_search_results(
    search_results: list[AlbumShort],
    page_num: int = 0,
) -> str:
    return ''.join(
        f'{html.bold(str(i))}. {album.name}\n\n'
        for i, album in enumerate(
            search_results, start=(1 + LIST_PAGE_LENGTH * page_num)
        )
    )


async def send_album_data(
    message: Message,
    album_slug: str,
    pending_downloads: dict,
) -> None:
    try:
        album = get_album(album_slug)
    except Exception:
        await message.answer("Couldn't get album data :-(")
        raise

    md5_hash = md5(album.slug.encode()).hexdigest()

    pending_downloads[md5_hash] = album.slug

    if album.thumbnail_urls:
        await message.reply_photo(URLInputFile(album.thumbnail_urls[0]))

    await message.reply(
        text=format_album_info(album),
        reply_markup=get_album_keyboard(md5_hash),
    )


async def send_audio_track(
    message: Message,
    track: AudioTrack,
    download_dir: Path,
) -> None:
    async def _send_track(from_):
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


def cache_album_list(
    album_list: list[AlbumShort],
    cached_lists: dict[str, list],
) -> str:
    list_md5 = md5(str(album_list).encode()).hexdigest()
    cached_lists[list_md5] = album_list

    return list_md5


async def send_album_list(
    message: Message,
    list_page: list[AlbumShort],
    list_md5: str,
    current_page_num: int,
    last_page_num: int,
) -> None:
    keyboard = get_list_select_keyboard(
        list_md5,
        current_page_num,
        last_page_num,
        len(list_page),
    )

    await message.answer(
        format_search_results(
            list_page,
            current_page_num,
        ),
        reply_markup=keyboard,
    )


def get_album_keyboard(download_hash: str) -> InlineKeyboardMarkup:
    download_button = InlineKeyboardButton(
        text='Download',
        callback_data=f'download_album://{download_hash}',
    )
    return InlineKeyboardMarkup(inline_keyboard=[[download_button]])


def get_list_select_keyboard(
    list_md5: str,
    current_page_num: int,
    last_page_num: int,
    page_len: int = LIST_PAGE_LENGTH,
):
    page_shift = LIST_PAGE_LENGTH * current_page_num
    select_keys = batch_collection(
        [
            InlineKeyboardButton(
                text=f'{i + page_shift + 1}',
                callback_data=(f'select://{list_md5};{i + page_shift}'),
            )
            for i in range(page_len)
        ],
        batch_size=5,
    )

    page_keys = [
        InlineKeyboardButton(
            text=f'[{current_page_num + 1}]',
            callback_data='dummy',
        )
    ]

    if current_page_num != 0:
        page_keys = [
            InlineKeyboardButton(
                text='<<',
                callback_data=f'page://{list_md5};0',
            ),
            InlineKeyboardButton(
                text='<',
                callback_data=f'page://{list_md5};{current_page_num - 1}',
            ),
        ] + page_keys

    if current_page_num != last_page_num:
        page_keys += [
            InlineKeyboardButton(
                text='>',
                callback_data=f'page://{list_md5};{current_page_num + 1}',
            ),
            InlineKeyboardButton(
                text='>>',
                callback_data=f'page://{list_md5};{last_page_num}',
            ),
        ]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            *select_keys,
            page_keys,
        ]
    )
