import os, urllib.parse, urllib.request
from dotenv import load_dotenv

print("-> Загружаю .env ...")
load_dotenv()

token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("CHAT_ID")

print("BOT_TOKEN ok?" , bool(token))
print("CHAT_ID   :", chat_id)

if not token or not chat_id:
    print("Ошибка: нет BOT_TOKEN или CHAT_ID в .env")
    raise SystemExit(1)

params = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": "Тест: бот добрался до чата ✅"
}).encode("utf-8")

url = f"https://api.telegram.org/bot{token}/sendMessage"
print("-> Делаю запрос к Telegram...")
req = urllib.request.Request(url, data=params, method="POST")
with urllib.request.urlopen(req) as resp:
    body = resp.read().decode("utf-8")
    print("HTTP", resp.status)
    print("Ответ Telegram:", body)
