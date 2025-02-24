import logging
import os
import random
import shutil

import khinsider
from telegram import Update
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


async def handle_track_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message

    while (
        download_id := random.randint(1, 999999)
    ) and download_id in context.bot_data['downloads']:
        pass

    download_path = khinsider.DOWNLOADS_PATH / str(download_id)
    context.bot_data['downloads']['download_id'] = download_path

    try:
        (track_path,) = await khinsider.download(message.text, download_path)
    except Exception:
        await message.reply_text("Couldn't get track :-(")
        raise
    else:
        while True:
            try:
                await message.reply_audio(track_path)
            except TimedOut:
                continue
            break
    finally:
        shutil.rmtree(download_path, ignore_errors=True)
        context.bot_data['downloads'].pop('download_id')


async def handle_album_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message

    try:
        album_data = khinsider.get_album_data(message.text)
    except khinsider.KhinsiderError:
        await message.reply_text("Couldn't get album data :-(")
        return

    await message.reply_photo(
        album_data.thumbnail_urls[0],
        caption=(
            f'{album_data.name}\n'
            f'Year: {album_data.year}\n'
            f'Type: {album_data.type}\n'
            f'Track count: {album_data.track_count}'
        ),
    )

    for download in khinsider.download_from_urls(message.text.splitlines()[0]):
        if not download:
            continue
        while True:
            try:
                await message.reply_audio(
                    download,
                    thumbnail=album_data.thumbnail_urls[0],
                )
            except TimedOut:
                continue
            break
        download.unlink(missing_ok=True)

    download.parent.rmdir()


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
