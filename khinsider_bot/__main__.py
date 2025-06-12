from argparse import ArgumentParser
from asyncio import run
from logging import (
    basicConfig as setup_logging,
    FileHandler,
    INFO,
    StreamHandler,
)
from os import getenv
from sys import stderr

from .asgi import webserver
from .bot import bot, dispatcher
from .constants import BOT_DATA_PATH
from .core import downloader


def construct_argparser() -> ArgumentParser:
    parser = ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('-w', '--webhook', action='store_true')
    modes.add_argument('-p', '--polling', action='store_true')

    return parser


async def main() -> None:
    args = construct_argparser().parse_args()

    setup_logging(
        level=INFO,
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
        handlers=[
            FileHandler(BOT_DATA_PATH / 'main.log'),
            StreamHandler(stderr),
        ],
    )

    if args.webhook:
        await bot.set_webhook(
            url=getenv('WEBHOOK_URL'),
            secret_token=getenv('WEBHOOK_TOKEN'),
        )

        await webserver.serve()
    elif args.polling:
        await dispatcher.start_polling(bot)

    downloader.shutdown()


if __name__ == '__main__':
    run(main())
