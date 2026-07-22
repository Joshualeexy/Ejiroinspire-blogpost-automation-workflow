import asyncio
from duckduckgo_search import DDGS
from crawl4ai import AsyncWebCrawler
from .base import ResearchProvider, ResearchReport, SearchResult

class Crawl4AiProvider(ResearchProvider):
    def __init__(self, config: dict = None):
        self.config = config or {}

    def search(self, query: str) -> ResearchReport:
        return asyncio.run(self._async_search(query))

    async def _async_search(self, query: str) -> ResearchReport:
        report = ResearchReport(query=query)
        try:
            # 1. Search DDG to get top URL
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=1))
                if not results:
                    return report
                top_url = results[0].get("href")
                title = results[0].get("title", "")
                snippet = results[0].get("body", "")

            # 2. Crawl the top URL
            if top_url:
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=top_url)
                    content = result.markdown if result and result.markdown else snippet
                    report.results.append(SearchResult(
                        url=top_url,
                        title=title,
                        content=content,
                        snippet=snippet
                    ))
        except Exception as e:
            print(f"Crawl4AI search failed: {e}")
        return report
