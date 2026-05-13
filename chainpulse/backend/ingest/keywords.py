"""Supply chain query terms reused across NewsAPI / Guardian / GNews."""
from __future__ import annotations

QUERY_TERMS = [
    "port strike OR port closure",
    "shipping delay OR freight delay",
    "factory shutdown OR plant closure",
    "trade sanctions OR trade embargo",
    "typhoon flood earthquake supply chain",
    "semiconductor shortage",
    "customs delay OR border closure",
]

RSS_FEEDS = [
    "https://www.hellenicshippingnews.com/feed/",
    "https://splash247.com/feed/",
    "https://www.wto.org/english/news_e/news_e.rss",
]
