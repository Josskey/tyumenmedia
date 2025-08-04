import asyncio
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
import json
import os
import re

# === Конфигурация ===
TOKEN = '7600186877:AAEew450qTbDLUmibIzK9a6AXho1Q6tpmUo'
CHAT_ID = -1002702700870  # ID канала
URL = 'https://72.ru/'

SEEN_FILE = 'seen_links.json'

# === Функции для работы с seen_links.json ===
def load_seen_links():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"[LOG] Загружено {len(data)} ранее отправленных ссылок.")
            return set(data)
    print("[LOG] Файл seen_links.json не найден. Начинаем с пустого списка.")
    return set()

def save_seen_links(seen):
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen), f, ensure_ascii=False)
    print(f"[LOG] Сохранено {len(seen)} ссылок в seen_links.json.")

# === Инициализация ===
seen_links = load_seen_links()
print(f"[LOG] seen_links при старте: {seen_links}")
bot = Bot(token=TOKEN)

pattern = re.compile(r'тюм', re.IGNORECASE)

async def fetch_page(session, url):
    async with session.get(url) as resp:
        return await resp.text()

async def parse_news(html):
    soup = BeautifulSoup(html, 'html.parser')
    news_items = []

    for a_tag in soup.select('a.link_8HoHw'):
        link = a_tag.get('href')
        if not link:
            continue

        title_tag = a_tag.select_one('div.title_8HoHw')
        title = title_tag.text.strip() if title_tag else 'Без заголовка'

        print(f"[DEBUG] Заголовок найден: {title}")

        if not pattern.search(title):
            continue

        news_items.append({'title': title, 'link': link, 'img': None})

    return news_items

async def send_news():
    async with aiohttp.ClientSession() as session:
        html = await fetch_page(session, URL)
        news_list = await parse_news(html)

        print(f"\nВсего новостей с «тюм» найдено: {len(news_list)}")
        new_news = [n for n in news_list if n['link'] not in seen_links]

        if not new_news:
            print("Нет новых новостей для публикации.\n")
            return

        for news in new_news:
            seen_links.add(news['link'])
            save_seen_links(seen_links)

            message = f"📰 {news['title']}\n{news['link']}"
            try:
                await bot.send_message(chat_id=CHAT_ID, text=message)
                print(f"✅ Отправлено: {news['title']}")
            except Exception as e:
                print(f"❌ Ошибка при отправке: {e}")

async def periodic_send():
    while True:
        await send_news()
        await asyncio.sleep(300)  # каждые 5 минут

if __name__ == '__main__':
    asyncio.run(periodic_send())
