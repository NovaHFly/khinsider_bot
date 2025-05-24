from os import getenv

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from uvicorn import Config, Server

from .bot import bot, dispatcher


async def telegram(request: Request) -> Response:
    await dispatcher.feed_webhook_update(
        bot=bot,
        update=await request.json(),
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

webserver = Server(
    config=Config(
        app=starlette_app,
        port=getenv('PORT'),
        host=getenv('HOSTNAME'),
    )
)
