import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from handlers.travel_handlers import router

# Load token from environment variable or token.env file
def load_token():
    # Try environment variable first
    token = os.getenv('BOT_TOKEN')
    
    if not token:
        # Try loading from token.env file
        try:
            with open('token.env', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('BOT_TOKEN'):
                        token = line.split('=', 1)[1].strip().strip("'\"")
                        break
        except FileNotFoundError:
            pass
    
    if not token:
        raise ValueError("BOT_TOKEN not found in environment variable or token.env file")
    
    return token


async def main():
    """Main function to start the bot"""
    token = load_token()
    
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Register router
    dp.include_router(router)
    
    # Start polling
    print("🤖 Bot is starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

