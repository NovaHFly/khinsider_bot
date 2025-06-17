import logging
import sys
from argparse import ArgumentParser
from asyncio import run
from os import getenv

from khinsider_bot.asgi import webserver
from khinsider_bot.bot import bot, dispatcher
from khinsider_bot.constants import BOT_DATA_PATH


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
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
        force=True,
        handlers=[
            logging.FileHandler(BOT_DATA_PATH / 'main.log'),
            logging.StreamHandler(sys.stdout),
        ],
    )

    if args.webhook:
        await bot.set_webhook(
            url=getenv('WEBHOOK_URL'),
            secret_token=getenv('WEBHOOK_TOKEN'),
        )

        await webserver.serve()
        await bot.delete_webhook(drop_pending_updates=True)
    elif args.polling:
        await dispatcher.start_polling(bot)


if __name__ == '__main__':
    run(main())
