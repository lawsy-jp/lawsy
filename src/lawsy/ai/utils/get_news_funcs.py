import os

import feedparser
import requests


def get_google_news(query, num_articles=4):
    """Google NewsのRSSフィードからニュースを取得する"""
    query = str(query).replace(" ", "+").replace("\n", "").replace("\t", "")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"

    feed = feedparser.parse(rss_url)
    articles = []
    for entry in feed.entries[:num_articles]:
        # `media_content` から画像 URL を取得
        image_url = None
        if "media_content" in entry:
            image_url = entry.media_content[0]["url"]
        if image_url is None:
            image_url = (
                "https://lh3.googleusercontent.com/"
                "J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc=s0-w300"
            )  # google newsのデフォルトサムネ

        articles.append(
            {"title": entry.title, "published": entry.published, "google_link": entry.link, "google_image": image_url}
        )

    return articles


# タイトルからURL他情報を取得する
# 🔹 APIキーとカスタム検索エンジン ID（cx）を設定
def get_infos_from_title(query):
    cse_key = os.environ["GOOGLE_CUSTOM_SEARCH_ENGINE_ACCESS_KEY"]
    cse_id = os.environ["GOOGLE_CUSTOM_SEARCH_ENGINE_ID"]
    url = "https://www.googleapis.com/customsearch/v1"

    params = {
        "q": f"{query}",
        "cx": cse_id,
        "key": cse_key,
        "num": 1,
    }

    response = requests.get(url, params=params)
    results = response.json()
    for item in results.get("items", []):
        title = item.get("title", None)
        link = item.get("link", None)

        og_image = None
        if "pagemap" in item and "metatags" in item["pagemap"]:
            for metatag in item["pagemap"]["metatags"]:
                if "og:image" in metatag:
                    og_image = metatag["og:image"]
                    break

        cse_image = None
        if "pagemap" in item and "cse_image" in item["pagemap"]:
            for image in item["pagemap"]["cse_image"]:
                if "src" in image:
                    cse_image = image["src"]
                    break
        # 結果をリストに追加
        article = {
            "original": query,
            "title": title,
            "searched_link": link,
            "og_image": og_image,
            "cse_image": cse_image,
        }
        return article

    return None


def collect_news_additional_infos(news):
    for i, article in enumerate(news):
        # collected = {}
        article_infos = get_infos_from_title(article["title"])
        image = news[i]["google_image"]
        link = news[i]["google_link"]

        if article_infos:
            news[i].update(
                {
                    "searched_link": article_infos.get("searched_link"),
                    "og_image": article_infos.get("og_image"),
                    "cse_image": article_infos.get("cse_image"),
                }
            )

            if news[i]["og_image"] is not None:
                image = news[i]["og_image"]
            elif news[i]["google_image"]:
                image = news[i]["google_image"]

            if news[i]["searched_link"] is not None:
                link = news[i]["searched_link"]
        news[i].update(
            {
                "image": image,
                "link": link,
            }
        )

    return news
