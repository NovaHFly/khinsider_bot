from asyncio import run
from logging import basicConfig as setup_logging, INFO
from os import getenv

from telegram import Update

from .asgi import webserver
from .bot import application
from .constants import BOT_DATA_PATH
from .core import downloader


async def main() -> None:
    setup_logging(
        level=INFO,
        filename=BOT_DATA_PATH / 'main.log',
        filemode='a',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    )
    await application.bot.set_webhook(
        url=getenv('WEBHOOK_URL'),
        allowed_updates=Update.ALL_TYPES,
    )

    # Run application and webserver together
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()

        downloader.shutdown()


if __name__ == '__main__':
    run(main())
