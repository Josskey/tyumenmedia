import asyncio
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
import json
import os
import hashlib

# === Конфигурация ===
TOKEN = '7600186877:AAEew450qTbDLUmibIzK9a6AXho1Q6tpmUo'
CHAT_ID = -1002702700870  # ID канала
SEEN_FILE = 'seen_links.json'

EDU_SOURCES = [
    'https://72.ru/text/education/',
    'https://tumentoday.ru/category/obrazovanie/',
    'https://don.admtyumen.ru/OIGV/doin/news/news.htm',
    'https://www.utmn.ru/news/stories/obrazovanie/',
    'https://park72.ru/category/education/',
    'https://tmn.kassir.ru/obrazovanie-i-kursy?sort=0',
    'https://tmn.kassir.ru/detskaya-afisha/?sort=0',
    'https://edo.72to.ru/news?page=1&per_page=9',
    'https://news.tyuiu.ru/latest'
]

# === Инициализация ===
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, 'r', encoding='utf-8') as f:
        seen = set(json.load(f))
else:
    seen = set()

bot = Bot(token=TOKEN)

# === Хеширование новости для избежания дублей ===
def hash_news(title):
    return hashlib.md5(title.lower().strip().encode()).hexdigest()

# === Сохранение ссылок ===
def save_seen():
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen), f, ensure_ascii=False)

async def fetch(session, url):
    async with session.get(url) as resp:
        return await resp.text()

async def parse_72(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for item in soup.select('div.content_RL97A'):
        a_tag = item.select_one('a.imgBg_RL97A')
        title_tag = item.select_one('a.header_RL97A')
        if not a_tag or not title_tag:
            continue
        link = a_tag['href']
        title = title_tag.text.strip()
        img = a_tag.get('style', '')
        img_url = None
        if 'url(' in img:
            img_url = img.split('url(')[-1].split(')')[0].strip("'\"")
            if img_url.startswith('/'):
                img_url = 'https://72.ru' + img_url
        articles.append({'title': title, 'link': link, 'img': img_url})
    return articles

async def parse_tumentoday(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for div in soup.select('div.news'):
        a_tag = div.find('a', class_='card-link')
        if not a_tag:
            continue
        link = 'https://tumentoday.ru' + a_tag['href']
        title = a_tag.get('title', 'Новость без заголовка')
        img = None  # Картинки часто нет
        articles.append({'title': title, 'link': link, 'img': img})
    return articles

async def parse_don(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for item in soup.select('div.news-item'):
        a_tag = item.find('a')
        if not a_tag:
            continue
        link = 'https://don.admtyumen.ru/' + a_tag['href'].lstrip('/')
        title = a_tag.get('title') or a_tag.text.strip()
        articles.append({'title': title, 'link': link, 'img': None})
    return articles

async def parse_utmn(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for item in soup.select('li.news-page_el'):
        a_tag = item.select_one('a.full')
        title_tag = item.select_one('div.article_title')
        if not a_tag or not title_tag:
            continue
        link = 'https://www.utmn.ru' + a_tag['href']
        title = title_tag.text.strip()
        img_tag = item.select_one('div.article_image img')
        img = img_tag['src'] if img_tag else None
        if img and img.startswith('/'):
            img = 'https://www.utmn.ru' + img
        articles.append({'title': title, 'link': link, 'img': img})
    return articles

async def parse_park72(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for article in soup.select('article'):
        a_tag = article.select_one('div.entry-image a')
        if not a_tag:
            continue
        link = a_tag['href']
        title_tag = article.select_one('header.entry-header')
        title = title_tag.get_text(strip=True) if title_tag else 'Новость без заголовка'
        articles.append({'title': title, 'link': link, 'img': None})
    return articles

async def parse_kassir(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for item in soup.select('article.recommendation-item'):
        a_tag = item.select_one('a[class*="recommendation-item_title"]')
        title = a_tag['title'] if a_tag else 'Без заголовка'
        link_tag = item.select_one('a.recommendation-item_img-block')
        href = link_tag['href'] if link_tag else ''
        link = base_url + href
        img_tag = link_tag.find('img') if link_tag else None
        img = img_tag['src'] if img_tag else None
        if img and img.startswith('/'):
            img = base_url + img
        articles.append({'title': title, 'link': link, 'img': img})
    return articles

async def parse_edo(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for a_tag in soup.select('a.kVhOWB'):
        link = 'https://edo.72to.ru' + a_tag['href']
        title = a_tag.get_text(strip=True)[:100]
        articles.append({'title': title, 'link': link, 'img': None})
    return articles

async def parse_tyuiu(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for a_tag in soup.select('a.group-link-underline'):
        link = a_tag['href']
        if not link.startswith('http'):
            link = 'https://news.tyuiu.ru' + link
        title_tag = a_tag.select_one('span.title')
        title = title_tag.get_text(strip=True) if title_tag else 'Без заголовка'
        img_tag = a_tag.select_one('img')
        img = img_tag['src'] if img_tag else None
        articles.append({'title': title, 'link': link, 'img': img})
    return articles

PARSERS = {
    'https://72.ru/text/education/': parse_72,
    'https://tumentoday.ru/category/obrazovanie/': parse_tumentoday,
    'https://don.admtyumen.ru/OIGV/doin/news/news.htm': parse_don,
    'https://www.utmn.ru/news/stories/obrazovanie/': parse_utmn,
    'https://park72.ru/category/education/': parse_park72,
    'https://tmn.kassir.ru/obrazovanie-i-kursy?sort=0': lambda html: parse_kassir(html, 'https://tmn.kassir.ru'),
    'https://tmn.kassir.ru/detskaya-afisha/?sort=0': lambda html: parse_kassir(html, 'https://tmn.kassir.ru'),
    'https://edo.72to.ru/news?page=1&per_page=9': parse_edo,
    'https://news.tyuiu.ru/latest': parse_tyuiu
}

async def send_news():
    async with aiohttp.ClientSession() as session:
        for url in EDU_SOURCES:
            try:
                html = await fetch(session, url)
                parser = PARSERS[url]
                news_items = await parser(html)

                for news in news_items:
                    news_hash = hash_news(news['title'])
                    if news_hash in seen:
                        continue

                    seen.add(news_hash)
                    save_seen()

                    msg = f"\U0001F4F0 <b>{news['title']}</b>\n{news['link']}"
                    try:
                        if news['img']:
                            await bot.send_photo(chat_id=CHAT_ID, photo=news['img'], caption=msg, parse_mode='HTML')
                        else:
                            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='HTML')
                        print(f"✅ Отправлено: {news['title']}")
                    except Exception as e:
                        print(f"❌ Ошибка при отправке: {e}")

            except Exception as e:
                print(f"[ERROR] Ошибка при парсинге {url}: {e}")

async def periodic():
    while True:
        await send_news()
        await asyncio.sleep(300)

if __name__ == '__main__':
    asyncio.run(periodic())
