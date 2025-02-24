import logging
import os
import random
import shutil
from pathlib import Path

import khinsider
from telegram import Message, Update
from telegram.constants import ReactionEmoji
from telegram.error import TimedOut
from telegram.ext import Application, ContextTypes, filters, MessageHandler

logger = logging.getLogger('khinsider_bot')


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


async def reply_with_album_details(
    message: Message,
    album: khinsider.Album,
) -> None:
    await message.reply_photo(
        album.thumbnail_urls[0],
        caption=(
            f'{album.name}\n'
            f'Year: {album.year}\n'
            f'Type: {album.type}\n'
            f'Track count: {album.track_count}'
        ),
    )


async def safe_reply_audio(
    message: Message,
    audio_path: Path,
) -> None:
    while True:
        try:
            await message.reply_audio(audio_path)
        except TimedOut:
            continue
        break


async def handle_track_url(
    message: Message,
    download_dir: Path,
) -> None:
    try:
        (track_path,) = khinsider.download(
            message.text.splitlines()[0],
            download_dir,
        )
        await safe_reply_audio(message, track_path)
    except Exception:
        await message.reply_text("Couldn't get track :-(")
        raise


async def handle_album_url(
    message: Message,
    download_dir: Path,
) -> None:
    try:
        album_data = khinsider.get_album_data(message.text)
        await reply_with_album_details(message, album_data)
        for track_path in khinsider.download(
            message.text.splitlines()[0],
            download_dir,
        ):
            await safe_reply_audio(message, track_path)
    except Exception:
        await message.reply_text("Couldn't get album data :-(")
        raise


@set_reaction_on_done(success_reaction=ReactionEmoji.THUMBS_UP)
async def handle_khinsider_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message

    await message.set_reaction(ReactionEmoji.EYES)

    while (
        download_id := random.randint(1, 999999)
    ) and download_id in context.bot_data['downloads']:
        pass

    download_dir = khinsider.DOWNLOADS_PATH / str(download_id)
    context.bot_data['downloads'][download_id] = download_dir

    try:
        if context.match[2]:
            await handle_track_url(message, download_dir)
            return

        await handle_album_url(message, download_dir)

    finally:
        shutil.rmtree(download_dir, ignore_errors=True)
        context.bot_data['downloads'].pop(download_id)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        filename='main.log',
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


if __name__ == '__main__':
    main()
