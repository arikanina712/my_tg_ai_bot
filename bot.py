import os, asyncio, logging, random, datetime, feedparser
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Нет BOT_TOKEN или CHAT_ID в .env")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
scheduler = AsyncIOScheduler()
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# === RSS-источники ===
FEEDS = [
    "https://habr.com/ru/rss/all/all/?fl=ru",
    "https://vc.ru/rss/all",
    "https://rb.ru/rss/"
]

def get_latest_news():
    items = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries[:3]:
            items.append(f"{e.title} — {e.link}")
    random.shuffle(items)
    return items[:5] or ["Нет новостей сегодня"]

# === Формирование prompt для GPT ===
def make_prompt():
    try:
        with open("brand_voice.md", "r", encoding="utf-8") as f:
            style = f.read()
    except FileNotFoundError:
        style = "Дружелюбный разговорный тон; тезис → инсайт → вопрос."
    return f"""Ты автор Telegram-канала про HR, карьеру и развитие.

Стиль:
{style}

Вот новости:
{get_latest_news()}

Сделай пост 900–1200 знаков:
— 1 тезис → 1 инсайт → 1 вопрос
— разговорный тон, без штампов и лишних тире
"""

# === Генерация изображения к посту ===
async def generate_image(prompt: str) -> str | None:
    if not client:
        return None
    try:
        img = client.images.generate(
            model="gpt-image-1",
            prompt=f"Иллюстрация для Telegram-поста в стиле HR-фильтр: {prompt}. "
                   f"Без текста, минимализм, чистый светлый фон, мягкие тени, спокойные цвета, "
                   f"подходит для квадрата 1:1.",
            size="1024x1024"
        )
        return img.data[0].url
    except Exception as e:
        logging.exception("Image generation error: %s", e)
        return None

# === Кнопки рейтинга ===
def rating_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Полезно", callback_data="rate_up"),
         InlineKeyboardButton(text="👎 Так себе", callback_data="rate_down")]
    ])

@router.callback_query(F.data.in_({"rate_up", "rate_down"}))
async def rate(cb):
    with open("ratings.csv", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()};{cb.data};{cb.from_user.id}\n")
    await cb.answer("Спасибо! Учтём.")

# === Кнопки выбора режима ===
def draft_mode_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Черновик (только текст)", callback_data="draft_text")],
        [InlineKeyboardButton(text="🖼 Черновик + картинка", callback_data="draft_image")]
    ])

@router.callback_query(F.data == "draft_text")
async def cb_draft_text(cb):
    await make_post(False)
    await cb.answer("Черновик без картинки отправлен.")

@router.callback_query(F.data == "draft_image")
async def cb_draft_image(cb):
    await make_post(True)
    await cb.answer("Черновик с картинкой отправлен.")

# === Генерация поста ===
async def make_post(with_image: bool = True):
    today = datetime.date.today().strftime("%d.%m.%Y")
    await bot.send_message(CHAT_ID, f"🤖 Проверка связи ({today})")

    text = "Нет OPENAI_API_KEY — отправляю заглушку."
    if client:
        try:
            resp = client.responses.create(model="gpt-4.1-mini", input=make_prompt())
            text = resp.output_text
        except Exception:
            logging.exception("OpenAI error")
            text = "Не удалось сгенерировать текст (проверь OPENAI_API_KEY)."

    caption = f"📰 Черновик поста {today}\n\n{text}\n\n#draft"

    if with_image:
        first_line = text.strip().splitlines()[0] if text.strip() else "HR и карьера"
        image_url = await generate_image(first_line[:120])
        if image_url:
            if len(caption) > 1000:
                await bot.send_photo(CHAT_ID, image_url)
                await bot.send_message(CHAT_ID, caption, reply_markup=rating_kb())
            else:
                await bot.send_photo(CHAT_ID, image_url, caption=caption, reply_markup=rating_kb())
            return

    await bot.send_message(CHAT_ID, caption, reply_markup=rating_kb())

# === Команды ===
@router.message(CommandStart())
async def on_start(m: Message):
    await m.reply("Привет! Выберите режим черновика:", reply_markup=draft_mode_kb())

@router.message(Command("draft"))
async def on_draft(m: Message):
    await make_post(False)
    await m.reply("Черновик отправлен без картинки.")

@router.message(Command("draft_image"))
async def on_draft_image(m: Message):
    await make_post(True)
    await m.reply("Черновик отправлен с картинкой.")

# === Расписание ===
@scheduler.scheduled_job("cron", hour=10, minute=0)
async def daily_job():
    await make_post()

# === Основной цикл ===
from aiohttp import web

async def health(_):
    return web.Response(text="ok")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    port = int(os.getenv("PORT", "10000"))  # Render задаёт PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"HTTP server started on 0.0.0.0:{port}")

async def main():
    # важно: мы работаем через long polling, поэтому убираем webhook
    await bot.delete_webhook(drop_pending_updates=True)
    scheduler.start()

    try:
        await bot.send_message(CHAT_ID, "✅ Бот запущен. Пишите /draft в ЛС боту.")
    except Exception:
        logging.exception("Не получилось написать в CHAT_ID при старте")

    logging.info("Стартуем polling…")
    # параллельно поднимаем health-сервер (чтобы Render видел открытый порт)
    await asyncio.gather(
        start_web(),
        dp.start_polling(bot, allowed_updates=["message", "callback_query"]),
    )

if __name__ == "__main__":
    asyncio.run(main())
