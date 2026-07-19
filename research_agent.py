import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ddgs import DDGS


@dataclass
class Source:
    title: str
    url: str
    domain: str


@dataclass
class ResearchResult:
    query: str
    official_url: Optional[str]
    facts: List[str] = field(default_factory=list)
    sources: List[Source] = field(default_factory=list)


class ResearchAgent:
    """Runs ONE web search per topic. Ranks results by domain trust tier to
    pick a likely official product URL, and compresses snippets into a short,
    deduplicated list of facts. Downstream generators only read what this
    returns — they never talk to the web directly."""

    # Excluded entirely from the "official URL" slot; still eligible as a
    # fact source since a Reddit thread can contain real info, just not
    # something we'd hand back as "the product's site".
    SOCIAL_FORUM_DOMAINS = {
        "reddit.com", "youtube.com", "facebook.com", "instagram.com",
        "pinterest.com", "quora.com", "tiktok.com", "x.com", "twitter.com",
    }
    MARKETPLACE_DOMAINS = {
        "amazon.com", "ebay.com", "walmart.com", "bestbuy.com",
        "aliexpress.com", "target.com", "newegg.com",
    }
    # Legitimate, but clearly not "the manufacturer" -- rank below unknown
    # domains, which are more likely to be the brand's own site.
    KNOWN_REVIEW_DOMAINS = {
        "theverge.com", "techradar.com", "tomsguide.com", "pcmag.com",
        "wired.com", "cnet.com", "rtings.com", "tomshardware.com",
        "engadget.com", "digitaltrends.com", "arstechnica.com",
        "androidcentral.com", "howtogeek.com", "zdnet.com",
    }
    LOW_VALUE_DOMAINS = {"wikipedia.org"}

    def __init__(self, max_results: int = 8, max_facts_chars: int = 1500):
        self.max_results = max_results
        self.max_facts_chars = max_facts_chars

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.lower().removeprefix("www.")

    BLOCKED_PATH_SEGMENTS = {
        "review",
        "blog",
        "press-release",
        "press_release",
        "article",
        "news",
        "comparison",
        "compare",
        "affiliate",
    }

    def _tier(self, domain: str) -> int:
        """Lower = more trustworthy as the 'official product page' pick.
        1 = unknown domain (most likely the brand's own site)
        2 = known review/reference site (legit, but not the manufacturer)
        3 = marketplace/social/forum (never picked as the official URL)"""
        if domain in self.MARKETPLACE_DOMAINS or domain in self.SOCIAL_FORUM_DOMAINS:
            return 3
        if domain in self.KNOWN_REVIEW_DOMAINS or domain in self.LOW_VALUE_DOMAINS:
            return 2
        return 1

    def _is_blocked_path(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(segment in path for segment in self.BLOCKED_PATH_SEGMENTS)

    def _select_official_url(self, scored: List[Dict[str, Any]]) -> Optional[str]:
        for result in scored:
            if result["tier"] != 1:
                continue
            if self._is_blocked_path(result["url"]):
                continue
            return result["url"]
        return None

    def research(self, query: str) -> ResearchResult:
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=self.max_results))
        except Exception as e:
            print(f"Research lookup failed for '{query}': {e}")
            return ResearchResult(query=query, official_url=None)

        scored = []
        for r in raw_results:
            url = r.get("href") or r.get("url")
            body = (r.get("body") or "").strip()
            if not url or not body:
                continue
            domain = self._domain(url)
            scored.append({
                "title": (r.get("title") or "").strip(),
                "url": url,
                "domain": domain,
                "body": body,
                "tier": self._tier(domain),
            })

        if not scored:
            return ResearchResult(query=query, official_url=None)

        scored.sort(key=lambda x: x["tier"])

        official_url = self._select_official_url(scored)
        facts = self._compress_facts(scored)
        sources = [Source(title=r["title"], url=r["url"], domain=r["domain"]) for r in scored]

        return ResearchResult(query=query, official_url=official_url, facts=facts, sources=sources)

    def _compress_facts(self, scored: List[Dict[str, Any]]) -> List[str]:
        """Splits snippets into sentence-ish chunks and drops near-duplicates,
        so three sources all saying 'WiFi 6E' collapse into one fact instead
        of wasting context three times over."""
        seen = set()
        facts: List[str] = []
        total_chars = 0

        for r in scored:
            for chunk in re.split(r"(?<=[.!?])\s+", r["body"]):
                chunk = chunk.strip()
                if len(chunk) < 15:
                    continue
                normalized = re.sub(r"\s+", " ", chunk.lower())
                if normalized in seen:
                    continue
                if total_chars + len(chunk) > self.max_facts_chars:
                    return facts
                seen.add(normalized)
                facts.append(chunk)
                total_chars += len(chunk)

        return facts