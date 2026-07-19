from dataclasses import dataclass, field
from typing import List

@dataclass
class SearchResult:
    url: str
    title: str
    content: str
    snippet: str = ""

@dataclass
class ResearchReport:
    query: str
    results: List[SearchResult] = field(default_factory=list)

class ResearchProvider:
    def search(self, query: str) -> ResearchReport:
        raise NotImplementedError
