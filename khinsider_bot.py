import logging
import os
import random
import shutil
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

import khinsider
from telegram import (
    Message,
    Update,
)
from telegram.constants import ReactionEmoji
from telegram.error import TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)

logger = logging.getLogger('khinsider_bot')

downloader = khinsider.Downloader(max_workers=8)

BOT_DATA_PATH = Path(os.getenv('BOT_DATA', './data'))
BOT_DATA_PATH.mkdir(exist_ok=True, parents=True)

ROOT_DOWNLOADS_PATH = BOT_DATA_PATH / 'downloads'
ROOT_DOWNLOADS_PATH.mkdir(exist_ok=True, parents=True)


SimpleMessageHandler = Callable[
    [Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]
]


def set_noticed_reaction(
    reaction: ReactionEmoji = ReactionEmoji.EYES,
) -> Callable[[SimpleMessageHandler], SimpleMessageHandler]:
    """Set reaction when bot has noticed the message."""

    def decorator(handler: SimpleMessageHandler) -> SimpleMessageHandler:
        @wraps(handler)
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            await update.message.set_reaction(reaction)
            await handler(update, context)

        return handler_wrapper

    return decorator


def set_success_reaction(
    reaction: ReactionEmoji = ReactionEmoji.THUMBS_UP,
) -> Callable[[SimpleMessageHandler], SimpleMessageHandler]:
    """Set reaction when bot has successfully finished the task."""

    def decorator(handler: SimpleMessageHandler) -> SimpleMessageHandler:
        @wraps(handler)
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            await handler(update, context)
            await update.message.set_reaction(reaction)

        return handler_wrapper

    return decorator


def set_error_reaction(
    reaction: ReactionEmoji = ReactionEmoji.SEE_NO_EVIL_MONKEY,
) -> Callable[[SimpleMessageHandler], SimpleMessageHandler]:
    """Set reaction when task was aborted due to an error."""

    def decorator(handler: SimpleMessageHandler) -> SimpleMessageHandler:
        @wraps(handler)
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            try:
                await handler(update, context)
            except Exception:
                await update.message.set_reaction(reaction)
                raise

        return handler_wrapper

    return decorator


@contextmanager
def setup_download(existing_downloads: dict | None = None) -> Iterator[Path]:
    """Setup download path and remove it when done."""
    if existing_downloads is None:
        existing_downloads = {}

    while (
        download_id := random.randint(1, 999999)
    ) and download_id in existing_downloads:
        pass

    download_dir = (ROOT_DOWNLOADS_PATH) / str(download_id)
    existing_downloads[download_id] = download_dir

    try:
        yield download_dir
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)
        existing_downloads.pop(download_id, None)


async def safe_reply_audio(
    message: Message,
    audio_location: Path | str,
) -> Message | None:
    """Send audio safely, retrying on telegram timeout."""
    while True:
        try:
            return await message.reply_audio(audio_location)
        except TimedOut:
            continue


async def handle_track_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    existing_downloads = context.bot_data['downloads']
    try:
        track_url = khinsider.get_track_data(
            message.text.splitlines()[0]
        ).mp3_url
    except Exception:
        await message.reply_text("Couldn't get track :-(")
        raise

    if await safe_reply_audio(message, track_url):
        return

    with setup_download(existing_downloads) as download_dir:
        (track_path,) = downloader.download(
            message.text.splitlines()[0],
            download_path=download_dir,
        )
        await safe_reply_audio(message, track_path)


async def handle_album_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message

    try:
        album = khinsider.get_album_data(
            message.text.split()[0],
        )
    except Exception:
        await message.reply_text("Couldn't get album data :-(")
        raise

    await message.reply_photo(
        album.thumbnail_urls[0],
        caption=(
            f'{album.name}\n'
            f'Year: {album.year}\n'
            f'Type: {album.type}\n'
            f'Track count: {album.track_count}'
        ),
    )

    with setup_download(context.bot_data['downloads']) as download_dir:
        for track in downloader.fetch_tracks(album.track_urls):
            if await safe_reply_audio(message, track.mp3_url):
                continue

            (track_path,) = downloader.download(track.page_url, download_dir)
            await safe_reply_audio(message, track_path)
            track_path.unlink(missing_ok=True)


@set_noticed_reaction(reaction=ReactionEmoji.EYES)
@set_error_reaction(reaction=ReactionEmoji.SEE_NO_EVIL_MONKEY)
@set_success_reaction(reaction=ReactionEmoji.THUMBS_UP)
async def handle_khinsider_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if context.match[2]:
        await handle_track_url(update, context)
        return

    await handle_album_url(update, context)


async def handle_start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.message.reply_text(
        'Hello! I am khinsider bot.'
        '\nI can download albums and tracks from downloads.khinsider.com.'
        '\nJust send me the album or track url.',
    )


async def handle_help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.message.reply_text(
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


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        filename=BOT_DATA_PATH / 'main.log',
        filemode='a',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    )
    application = (
        Application.builder()
        .token(os.getenv('TELEGRAM_TOKEN'))
        .read_timeout(30)
        .write_timeout(35)
        .build()
    )

    application.add_handler(
        MessageHandler(
            filters.Regex(khinsider.KHINSIDER_URL_REGEX),
            handle_khinsider_url,
        )
    )
    application.add_handler(CommandHandler('start', handle_start_command))
    application.add_handler(CommandHandler('help', handle_help_command))

    application.bot_data['downloads'] = {}
    application.run_polling()
    downloader.shutdown()


if __name__ == '__main__':
    main()
