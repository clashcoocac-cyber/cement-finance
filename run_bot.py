"""
Bot entrypoint
Run this script to start the bot
"""
if __name__ == "__main__":
    from bot.main import main
    import asyncio
    
    asyncio.run(main())
