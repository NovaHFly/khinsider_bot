import logging
import os
import random
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
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


def set_reaction_on_done(
    handler=None,
    *,
    success_reaction: ReactionEmoji | None = None,
    error_reaction: ReactionEmoji | None = ReactionEmoji.SEE_NO_EVIL_MONKEY,
):
    def decorator(handler):
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ):
            try:
                result = await handler(update, context)
                await update.message.set_reaction(success_reaction)
                return result
            except Exception:
                await update.message.set_reaction(error_reaction)
                raise

        return handler_wrapper

    if handler:
        return decorator(handler)

    return decorator


@contextmanager
def setup_download(existing_downloads: dict | None = None) -> Iterator[Path]:
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

        if not await safe_reply_audio(message, track_url):
            with setup_download(existing_downloads) as download_dir:
                (track_path,) = downloader.download(
                    message.text.splitlines()[0],
                    download_path=download_dir,
                )
                await safe_reply_audio(message, track_path)
    except Exception:
        await message.reply_text("Couldn't get track :-(")
        raise


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
        for track in album.tracks:
            if track.mp3_url and await safe_reply_audio(
                message,
                track.mp3_url,
            ):
                return

            (track_path,) = downloader.download(track.page_url, download_dir)
            await safe_reply_audio(message, track_path)
            track_path.unlink(missing_ok=True)


@set_reaction_on_done(success_reaction=ReactionEmoji.THUMBS_UP)
async def handle_khinsider_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    await message.set_reaction(ReactionEmoji.EYES)

    if context.match[2]:
        await handle_track_url(update, context)
        return

    await handle_album_url(update, context)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        filename=BOT_DATA_PATH / 'main.log',
        filemode='a',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    )
    application = (
        Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    )
    application.add_handler(
        MessageHandler(
            filters.Regex(khinsider.KHINSIDER_URL_REGEX),
            handle_khinsider_url,
        )
    )
    application.bot_data['downloads'] = {}
    application.run_polling()
    downloader.shutdown()


if __name__ == '__main__':
    main()
