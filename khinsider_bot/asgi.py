import os

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from telegram import Update

from .bot import application


async def telegram(request: Request) -> Response:
    await application.update_queue.put(
        Update.de_json(data=await request.json(), bot=application.bot)
    )
    return Response()


async def health(_: Request) -> PlainTextResponse:
    """For the health endpoint, reply with a simple plain text message."""
    return PlainTextResponse(content='The bot is still running fine :)')


starlette_app = Starlette(
    routes=[
        Route('/', telegram, methods=['POST']),
        Route('/healthcheck/', health, methods=['GET']),
    ]
)

webserver = uvicorn.Server(
    config=uvicorn.Config(
        app=starlette_app,
        use_colors=False,
        port=os.getenv('PORT'),
        host=os.getenv('HOSTNAME'),
    )
)
