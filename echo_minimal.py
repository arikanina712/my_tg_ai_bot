import os, asyncio, logging
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Нет BOT_TOKEN в .env")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
r = Router()
dp.include_router(r)

@r.message(CommandStart())
async def start(m: Message):
    await m.reply("я жив! напиши /ping")

@r.message(Command("ping"))
async def ping(m: Message):
    await m.reply("pong")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)  # важно!
    print(">> starting polling")
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    asyncio.run(main())
