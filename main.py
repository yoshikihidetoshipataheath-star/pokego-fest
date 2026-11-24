import os
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

TEST_MODE = True

NEWS_URL = "https://pokemongolive.com"

KEYWORDS = [
    "go fest",
    "go-fest",
    "gofest",
    "goフェスト",
    "go フェスト",
]

RECORD_FILE = "notified_urls.txt"


def load_notified_urls():
    if not os.path.exists(RECORD_FILE):
        return set()
    urls = set()
    with open(RECORD_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.add(line)
    return urls


def save_notified_urls(urls):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        f.write("# 通知済みURLの記録用ファイル（自動更新されます）\n")
        for url in sorted(urls):
            f.write(url + "\n")


def normalize_url(href):
    full_url = urljoin("https://pokemongolive.com", href)
    parsed = urlparse(full_url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean_url.rstrip("/")


def fetch_news_list():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(NEWS_URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    articles = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not ("/news/" in href or "/post/" in href):
            continue
        if re.search(r"/news/?(\?.*)?$", href) or "/page/" in href:
            continue

        clean_url = normalize_url(href)
        if clean_url in seen:
            continue

        title = a_tag.get_text(" ", strip=True)
        if not title:
            continue

        seen.add(clean_url)
        articles.append({
            "title": title,
            "clean_url": clean_url,
            "ja_url": f"{clean_url}?hl=ja",
        })

    return articles


def is_go_fest_article(article):
    target_text = f"{article['title']} {article['clean_url']}".lower()
    return any(keyword in target_text for keyword in KEYWORDS)


def send_discord_notification(webhook_url, article, is_test=False):
    if is_test:
        header = "🧪 **【テスト通知】Pokémon GO 最新ニュース**"
    else:
        header = "🎉 **Pokémon GO Fest 関連ニュースを検知しました！**"

    message = f"{header}\n**{article['title']}**\n{article['ja_url']}"

    response = requests.post(
        webhook_url,
        json={"content": message},
        timeout=15,
    )
    response.raise_for_status()


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise ValueError(
            "DISCORD_WEBHOOK_URL が設定されていません。"
            "GitHubの Secrets に登録されているか確認してください。"
        )

    notified_urls = load_notified_urls()
    articles = fetch_news_list()
    print(f"取得した記事数: {len(articles)} 件")

    if not articles:
        print("記事が見つかりませんでした。")
        return

    if TEST_MODE:
        latest_article = articles
        print(f"テスト通知を送信します: {latest_article['title']}")
        send_discord_notification(webhook_url, latest_article, is_test=True)
        print("テスト通知の送信に成功しました！")
        return

    new_count = 0
    for article in articles:
        if article["clean_url"] in notified_urls:
            continue
        if not is_go_fest_article(article):
            continue

        print(f"新規検知！通知を送信します: {article['title']}")
        send_discord_notification(webhook_url, article, is_test=False)
        notified_urls.add(article["clean_url"])
        new_count += 1

    if new_count > 0:
        save_notified_urls(notified_urls)
        print(f"{new_count} 件の通知を送信し、記録を更新しました。")
    else:
        print("新しい GO Fest 関連の記事はありませんでした。")


if __name__ == "__main__":
    main()
