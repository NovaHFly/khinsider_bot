import asyncio
import logging
import os

import uvicorn
from telegram import Update

from .asgi import starlette_app
from .bot import application
from .constants import BOT_DATA_PATH
from .core import downloader


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        filename=BOT_DATA_PATH / 'main.log',
        filemode='a',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    )
    await application.bot.set_webhook(
        url=os.getenv('WEBHOOK_URL'),
        allowed_updates=Update.ALL_TYPES,
    )

    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            use_colors=False,
            port=os.getenv('PORT'),
            host=os.getenv('HOSTNAME'),
        )
    )

    # Run application and webserver together
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()

        downloader.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
