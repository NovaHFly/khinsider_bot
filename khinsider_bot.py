import logging
import os
from concurrent.futures import as_completed

import khinsider
from telegram import Update
from telegram.constants import ReactionEmoji
from telegram.ext import Application, ContextTypes, filters, MessageHandler

logger = logging.getLogger('khinsider_bot')


def unset_reaction_on_done(handler):
    async def handler_wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        result = await handler(update, context)
        await update.message.set_reaction()
        return result

    return handler_wrapper


async def handle_track_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message

    try:
        _, track_path = khinsider.fetch_and_download_track(message.text)
    except khinsider.KhinsiderError:
        await message.reply_text("Couldn't get track :-(")
        return

    await message.reply_audio(track_path)

    track_path.unlink(missing_ok=True)


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

    for task in as_completed(khinsider.download_tracks(message.text)):
        if task.exception():
            logger.error(task.exception())
            continue

        track_path = task.result()[1]
        await message.reply_audio(track_path)
        track_path.unlink(missing_ok=True)


@unset_reaction_on_done
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
    application.run_polling()


if __name__ == '__main__':
    main()
