"""
Main bot application
"""
import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Dispatcher, Bot, F
from aiogram.types import BotCommand

from bot.config.settings import load_env, get_settings
from bot.handlers import start_router, phone_router
from bot.middlewares import LoggingMiddleware


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Set bot commands"""
    commands = [
        BotCommand(command="start", description="Botni boshlash"),
        BotCommand(command="help", description="Yordam"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands set successfully")


async def main():
    """Main function"""
    bot = None
    try:
        # Load environment variables
        load_env()
        settings = get_settings()
        
        logger.info("Starting Cement Finance Bot...")
        
        # Initialize bot and dispatcher
        bot = Bot(token=settings.BOT_TOKEN)
        dp = Dispatcher()
        
        # Setup middlewares
        dp.message.middleware(LoggingMiddleware())
        
        # Setup routers
        dp.include_router(start_router)
        dp.include_router(phone_router)
        
        # Set bot commands
        await set_bot_commands(bot)
        
        # Start polling
        logger.info("Bot is running... (polling mode)")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set up .env file first:")
        logger.error("  1. cp .env.example .env")
        logger.error("  2. Edit .env and add BOT_TOKEN")
        logger.error("  3. Get token from @BotFather on Telegram")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if bot is not None:
            await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
