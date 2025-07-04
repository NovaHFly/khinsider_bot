import logging
import sys
from argparse import ArgumentParser
from asyncio import run

from khinsider.cache import CacheManager

from khinsider_bot.asgi import webserver
from khinsider_bot.bot import bot, dispatcher
from khinsider_bot.config import TELEGRAM_SECRET_TOKEN, TELEGRAM_WEBHOOK_URL
from khinsider_bot.constants import BOT_DATA_PATH

cache_manager = CacheManager.get_manager()


def construct_argparser() -> ArgumentParser:
    parser = ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('-w', '--webhook', action='store_true')
    modes.add_argument('-p', '--polling', action='store_true')

    return parser


async def main() -> None:
    args = construct_argparser().parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s, %(levelname)s, [%(funcName)s] %(message)s, %(name)s'
        ),
        force=True,
        handlers=[
            logging.FileHandler(BOT_DATA_PATH / 'main.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    try:
        if args.webhook:
            await bot.set_webhook(
                url=TELEGRAM_WEBHOOK_URL,
                secret_token=TELEGRAM_SECRET_TOKEN,
            )

            await webserver.serve()
            await bot.delete_webhook(drop_pending_updates=True)
        elif args.polling:
            await dispatcher.start_polling(bot)
    finally:
        cache_manager.stop_garbage_collector()


if __name__ == '__main__':
    run(main())
