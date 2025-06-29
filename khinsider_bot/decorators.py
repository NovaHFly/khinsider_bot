from collections.abc import Callable
from functools import wraps

from aiogram.dispatcher.event.handler import CallbackType
from aiogram.types import Message, ReactionTypeEmoji

from .enums import Emoji


def react_before(
    emoji: Emoji = Emoji.EYES,
) -> Callable[[CallbackType], CallbackType]:
    """Set reaction when bot has noticed the message."""

    def decorator(handler: CallbackType) -> CallbackType:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            await message.react([ReactionTypeEmoji(emoji=emoji)])
            await handler(message, *args, **kwargs)

        return handler_wrapper

    return decorator


def react_after(
    emoji: Emoji = Emoji.THUMBS_UP,
) -> Callable[[CallbackType], CallbackType]:
    """Set reaction when bot has successfully finished the task."""

    def decorator(handler: CallbackType) -> CallbackType:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            await handler(message, *args, **kwargs)
            await message.react([ReactionTypeEmoji(emoji=emoji)])

        return handler_wrapper

    return decorator


def react_on_error(
    emoji: Emoji = Emoji.SEE_NO_EVIL,
) -> Callable[[CallbackType], CallbackType]:
    """Set reaction when task was aborted due to an error."""

    def decorator(handler: CallbackType) -> CallbackType:
        @wraps(handler)
        async def handler_wrapper(message: Message, *args, **kwargs) -> None:
            try:
                await handler(message, *args, **kwargs)
            except Exception:
                await message.react([ReactionTypeEmoji(emoji=emoji)])
                return

        return handler_wrapper

    return decorator
