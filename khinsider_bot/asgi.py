from concurrent.futures import ThreadPoolExecutor

from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from uvicorn import Config, Server

from .bot import bot, dispatcher
from .config import WEBSERVER_HOST, WEBSERVER_PORT

executor = ThreadPoolExecutor(max_workers=5)


async def telegram(request: Request) -> Response:
    task = BackgroundTask(
        dispatcher.feed_webhook_update,
        bot=bot,
        update=await request.json(),
    )
    return Response(background=task)


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
        port=WEBSERVER_PORT,
        host=WEBSERVER_HOST,
    )
)
