"""Fetch stock market news from RSS feeds using Python's standard library."""

import argparse
from email.utils import parsedate_to_datetime
import html
import json
from pathlib import Path
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "PASGLLM-NewsFetcher/0.1 (+https://github.com/GamequadDev/PASGLLM)"

MARKET_RSS_FEEDS = {
    "google_news": "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={gl}:{lang}",
    "yahoo_finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={query}&region=US&lang=en-US",
}


class NewsDataError(RuntimeError):
    """Could not fetch or parse stock market news from the RSS feed."""


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_pub_date(raw_date: str | None) -> str | None:
    if not raw_date:
        return None
    try:
        return parsedate_to_datetime(raw_date.strip()).isoformat()
    except (TypeError, ValueError, IndexError):
        return raw_date.strip()


def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    system_ca = Path("/etc/ssl/cert.pem")
    if system_ca.is_file():
        return ssl.create_default_context(cafile=str(system_ca))
    return ssl.create_default_context()


def _fetch_rss_xml(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout, context=_build_ssl_context()) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise NewsDataError(f"Failed to fetch RSS feed from {url}: {exc}") from exc


def _parse_rss_items(xml_bytes: bytes, limit: int) -> list[dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise NewsDataError(f"Invalid RSS XML response: {exc}") from exc

    items = []
    for item in root.findall(".//item")[:limit]:
        source_el = item.find("source")
        items.append({
            "title": _clean_text(item.findtext("title")),
            "link": _clean_text(item.findtext("link")),
            "published_at": _parse_pub_date(item.findtext("pubDate")),
            "source": _clean_text(source_el.text if source_el is not None else None),
            "summary": _clean_text(item.findtext("description")),
        })
    return items


def build_feed_url(
    query: str,
    provider: str = "google_news",
    lang: str = "en",
    country: str = "US",
) -> str:
    """Build an RSS feed URL for a ticker or company query."""
    if provider not in MARKET_RSS_FEEDS:
        supported = ", ".join(sorted(MARKET_RSS_FEEDS))
        raise ValueError(f"Unsupported provider '{provider}'. Choose from: {supported}.")

    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query must not be empty.")

    hl = f"{lang}-{country}" if lang != country.lower() else lang
    return MARKET_RSS_FEEDS[provider].format(
        query=quote_plus(cleaned),
        hl=hl,
        gl=country.upper(),
        lang=lang.lower(),
    )


def fetch_stock_news(
    query: str,
    limit: int = 10,
    provider: str = "google_news",
    lang: str = "en",
    country: str = "US",
    feed_url: str | None = None,
) -> dict:
    """Fetch and parse stock market news items from an RSS feed."""
    if limit < 1:
        raise ValueError("limit must be at least 1.")

    target_url = feed_url or build_feed_url(
        query=query,
        provider=provider,
        lang=lang,
        country=country,
    )
    xml_bytes = _fetch_rss_xml(target_url)
    articles = _parse_rss_items(xml_bytes, limit=limit)

    return {
        "query": query.strip(),
        "provider": "custom" if feed_url else provider,
        "feed_url": target_url,
        "count": len(articles),
        "articles": articles,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch stock market news from RSS feeds.")
    parser.add_argument("query", help="Ticker or company name, e.g. NVDA or 'Vigo Photonics'")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of articles")
    parser.add_argument(
        "--provider",
        choices=sorted(MARKET_RSS_FEEDS),
        default="google_news",
        help="RSS feed provider",
    )
    parser.add_argument("--lang", default="en", help="Language code, e.g. en or pl")
    parser.add_argument("--country", default="US", help="Country code, e.g. US or PL")
    parser.add_argument("--feed-url", default=None, help="Optional custom RSS feed URL")
    args = parser.parse_args()

    try:
        result = fetch_stock_news(
            query=args.query,
            limit=args.limit,
            provider=args.provider,
            lang=args.lang,
            country=args.country,
            feed_url=args.feed_url,
        )
    except ValueError as exc:
        parser.error(str(exc))
    except NewsDataError as exc:
        parser.exit(1, f"{exc}\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
