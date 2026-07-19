from duckduckgo_search import DDGS
from .base import ResearchProvider, ResearchReport, SearchResult

class DuckDuckGoProvider(ResearchProvider):
    def __init__(self, config: dict = None):
        self.config = config or {}

    def search(self, query: str) -> ResearchReport:
        report = ResearchReport(query=query)
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                for r in results:
                    report.results.append(SearchResult(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        content=r.get("body", ""),
                        snippet=r.get("body", "")
                    ))
        except Exception as e:
            print(f"DDG Search failed: {e}")
        return report
