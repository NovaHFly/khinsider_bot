from logging import getLogger
from os import getenv

from khinsider import get_album_data, get_track_data, KHINSIDER_URL_REGEX
from telegram import Update
from telegram.constants import ReactionEmoji
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)

from .core import downloader
from .decorators import (
    set_error_reaction,
    set_noticed_reaction,
    set_success_reaction,
)
from .util import safe_reply_audio, setup_download

# TODO: Add logging
logger = getLogger('khinsider_bot')


async def handle_track_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    existing_downloads = context.bot_data['downloads']
    try:
        track_url = get_track_data(message.text.splitlines()[0]).mp3_url
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
        album = get_album_data(
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


application = (
    Application.builder()
    .token(getenv('TELEGRAM_TOKEN'))
    .read_timeout(30)
    .write_timeout(35)
    .updater(None)
    .build()
)

application.add_handler(
    MessageHandler(
        filters.Regex(KHINSIDER_URL_REGEX),
        handle_khinsider_url,
    )
)
application.add_handler(CommandHandler('start', handle_start_command))
application.add_handler(CommandHandler('help', handle_help_command))

application.bot_data['downloads'] = {}
