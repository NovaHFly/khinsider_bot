from collections.abc import Awaitable, Callable
from functools import wraps

from telegram import Update
from telegram.constants import ReactionEmoji
from telegram.ext import ContextTypes

SimpleMessageHandler = Callable[
    [Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]
]


def set_noticed_reaction(
    reaction: ReactionEmoji = ReactionEmoji.EYES,
) -> Callable[[SimpleMessageHandler], SimpleMessageHandler]:
    """Set reaction when bot has noticed the message."""

    def decorator(handler: SimpleMessageHandler) -> SimpleMessageHandler:
        @wraps(handler)
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            await update.message.set_reaction(reaction)
            await handler(update, context)

        return handler_wrapper

    return decorator


def set_success_reaction(
    reaction: ReactionEmoji = ReactionEmoji.THUMBS_UP,
) -> Callable[[SimpleMessageHandler], SimpleMessageHandler]:
    """Set reaction when bot has successfully finished the task."""

    def decorator(handler: SimpleMessageHandler) -> SimpleMessageHandler:
        @wraps(handler)
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            await handler(update, context)
            await update.message.set_reaction(reaction)

        return handler_wrapper

    return decorator


def set_error_reaction(
    reaction: ReactionEmoji = ReactionEmoji.SEE_NO_EVIL_MONKEY,
) -> Callable[[SimpleMessageHandler], SimpleMessageHandler]:
    """Set reaction when task was aborted due to an error."""

    def decorator(handler: SimpleMessageHandler) -> SimpleMessageHandler:
        @wraps(handler)
        async def handler_wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
        ) -> None:
            try:
                await handler(update, context)
            except Exception:
                await update.message.set_reaction(reaction)
                raise

        return handler_wrapper

    return decorator
