from collections.abc import Awaitable, Callable
from functools import wraps

from aiogram.types import Message, ReactionTypeEmoji

from .enums import ReactionEmoji


def set_noticed_reaction(
    reaction: ReactionEmoji = ReactionEmoji.EYES,
) -> Callable[[Awaitable], Awaitable]:
    """Set reaction when bot has noticed the message."""

    def decorator(handler: Awaitable) -> Awaitable:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            await message.react([ReactionTypeEmoji(emoji=reaction)])
            await handler(message, *args, **kwargs)

        return handler_wrapper

    return decorator


def set_success_reaction(
    reaction: ReactionEmoji = ReactionEmoji.THUMBS_UP,
) -> Callable[[Awaitable], Awaitable]:
    """Set reaction when bot has successfully finished the task."""

    def decorator(handler: Awaitable) -> Awaitable:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            await handler(message, *args, **kwargs)
            await message.react([ReactionTypeEmoji(emoji=reaction)])

        return handler_wrapper

    return decorator


def set_error_reaction(
    reaction: ReactionEmoji = ReactionEmoji.SEE_NO_EVIL,
) -> Callable[[Awaitable], Awaitable]:
    """Set reaction when task was aborted due to an error."""

    def decorator(handler: Awaitable) -> Awaitable:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            try:
                await handler(message, *args, **kwargs)
            except Exception:
                await message.react([ReactionTypeEmoji(emoji=reaction)])
                raise

        return handler_wrapper

    return decorator
