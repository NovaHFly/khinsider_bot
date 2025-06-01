from collections.abc import Awaitable, Callable
from functools import wraps

from aiogram.types import Message, ReactionTypeEmoji

from .enums import Emoji


def react_before(
    emoji: Emoji = Emoji.EYES,
) -> Callable[[Awaitable], Awaitable]:
    """Set reaction when bot has noticed the message."""

    def decorator(handler: Awaitable) -> Awaitable:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            await message.react([ReactionTypeEmoji(emoji=emoji)])
            await handler(message, *args, **kwargs)

        return handler_wrapper

    return decorator


def react_after(
    emoji: Emoji = Emoji.THUMBS_UP,
) -> Callable[[Awaitable], Awaitable]:
    """Set reaction when bot has successfully finished the task."""

    def decorator(handler: Awaitable) -> Awaitable:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            await handler(message, *args, **kwargs)
            await message.react([ReactionTypeEmoji(emoji=emoji)])

        return handler_wrapper

    return decorator


def react_on_error(
    emoji: Emoji = Emoji.SEE_NO_EVIL,
) -> Callable[[Awaitable], Awaitable]:
    """Set reaction when task was aborted due to an error."""

    def decorator(handler: Awaitable) -> Awaitable:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            try:
                await handler(message, *args, **kwargs)
            except Exception:
                await message.react([ReactionTypeEmoji(emoji=emoji)])
                raise

        return handler_wrapper

    return decorator
