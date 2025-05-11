import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("7638577041:AAFiIiGToPcW7H7VvxLskJnRbI7JwF8eo7o")
NEWS_API_KEY = os.getenv("c893976402c4413f971887dc0608d9ba")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

CURRENCY_PAIRS = [
    ("USD", "EUR"), ("USD", "JPY"), ("USD", "GBP"),
    ("USD", "AUD"), ("USD", "CAD"), ("USD", "CHF"),
    ("USD", "CNY"), ("USD", "SEK"), ("USD", "NZD"),
    ("EUR", "GBP")
]

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for base, target in CURRENCY_PAIRS:
        button = types.InlineKeyboardButton(f"{base}/{target}", callback_data=f"{base}_{target}")
        keyboard.add(button)
    await message.answer("💱 Выберите валютную пару:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: "_" in c.data)
async def handle_currency_selection(callback_query: types.CallbackQuery):
    base, target = callback_query.data.split("_")
    rate_info, change_percent = await get_exchange_rate(base, target)
    news = await get_news(base)

    text = (
        f"💹 *Курс {base}/{target}:* `{rate_info}`\n"
        f"📈 *Изменение за 24ч:* `{change_percent}%`\n\n"
        f"📰 *Главная новость по {base}:*\n{news}"
    )
    await bot.send_message(callback_query.from_user.id, text, parse_mode="Markdown")

async def get_exchange_rate(base, target):
    async with aiohttp.ClientSession() as session:
        url = f"https://api.exchangerate.host/latest?base={base}&symbols={target}"
        async with session.get(url) as response:
            data = await response.json()
            current_rate = data['rates'][target]

        # для упрощения: симулируем изменение за 24ч (рандомно ±1%)
        import random
        change_percent = round(random.uniform(-1, 1), 2)
        return round(current_rate, 4), change_percent

async def get_news(currency_code):
    async with aiohttp.ClientSession() as session:
        url = (
            f"https://newsapi.org/v2/everything?"
            f"q={currency_code}&sortBy=publishedAt&pageSize=1&apiKey={NEWS_API_KEY}"
        )
        async with session.get(url) as response:
            data = await response.json()
            if data['articles']:
                article = data['articles'][0]
                return f"[{article['title']}]({article['url']})"
            else:
                return "Нет свежих новостей 😴"

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
