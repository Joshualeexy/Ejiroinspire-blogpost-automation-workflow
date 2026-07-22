import asyncio
import os
from pathlib import Path

# crawl4ai tries to create ~/.crawl4ai at import time, which fails on
# read-only home directories.  Point it at the project directory instead.
if "CRAWL4_AI_BASE_DIRECTORY" not in os.environ:
    os.environ["CRAWL4_AI_BASE_DIRECTORY"] = str(Path(__file__).resolve().parent.parent)

from ddgs import DDGS
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
            # 1. Search DDG to get top URLs (get more results for better coverage)
            with DDGS() as ddgs:
                # Use lite backend if auto fails or returns 0 inconsistently, but auto is usually fine.
                # Changing to 'lite' specifically to bypass '0 results' bot protections on datacenter IPs.
                results = list(ddgs.text(query, max_results=3, backend="lite"))
                if not results:
                    return report
                
                # Try multiple URLs until we get content or exhaust options
                successful_crawls = 0
                for r in results[:3]:  # Process up to 3 results
                    try:
                        url = r.get("href", "")
                        title = r.get("title", "")
                        snippet = r.get("body", "")
                        
                        if not url:
                            continue
                            
                        # Crawl the URL
                        async with AsyncWebCrawler() as crawler:
                            result = await crawler.arun(url=url)
                            content = result.markdown if result and result.markdown else snippet
                            
                            if content.strip():  # Only add results with actual content
                                report.results.append(SearchResult(
                                    url=url,
                                    title=title,
                                    content=content,
                                    snippet=snippet
                                ))
                                successful_crawls += 1
                                
                    except Exception as e:
                        print(f"Failed to crawl {url}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Crawl4AI search failed: {e}")
            
        return report
