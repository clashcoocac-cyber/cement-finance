"""
Logging middleware for aiogram
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging events"""
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        """
        Log incoming event and call handler
        """
        try:
            if isinstance(event, Message):
                if event.text:
                    logger.info(
                        f"Message from {event.from_user.id} "
                        f"(@{event.from_user.username}): {event.text[:50]}"
                    )
                elif event.contact:
                    logger.info(
                        f"Contact from {event.from_user.id} "
                        f"(@{event.from_user.username}): {event.contact.phone_number}"
                    )
            elif isinstance(event, CallbackQuery):
                logger.info(
                    f"Callback from {event.from_user.id} "
                    f"(@{event.from_user.username}): {event.data}"
                )
        except Exception as e:
            logger.debug(f"Logging error: {e}")
        
        return await handler(event, data)
