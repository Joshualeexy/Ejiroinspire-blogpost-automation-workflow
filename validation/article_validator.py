from dataclasses import dataclass, field
from typing import List
from generators.classifier import ArticleType

@dataclass
class ValidationIssue:
    check: str
    message: str
    severity: str = "error"  # "error" or "warning"

@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

class ArticleValidator:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.min_words = 500
        self.banned_phrases = [
            "in today's fast-paced world",
            "whether you're a beginner or expert",
            "when it comes to",
            "dive deep",
            "delve into"
        ]

    def validate(self, content: str, article_type: ArticleType) -> ValidationReport:
        report = ValidationReport()
        if not content:
            report.issues.append(ValidationIssue("content_present", "Content is empty."))
            return report

        # Word count check
        word_count = len(content.split())
        if word_count < self.min_words:
            report.issues.append(ValidationIssue("word_count", f"Article only has {word_count} words (min {self.min_words})."))

        # Banned phrases check
        content_lower = content.lower()
        for phrase in self.banned_phrases:
            if phrase in content_lower:
                report.issues.append(ValidationIssue("banned_phrase", f"Found banned phrase: '{phrase}'", severity="warning"))

        # Outline structure check (basic)
        if "##" not in content:
            report.issues.append(ValidationIssue("markdown_structure", "Missing Markdown headings (H2)."))

        # Image placeholder check
        if "![Descriptive alt text for the image](PLACEHOLDER)" not in content and "![Descriptive alt text" not in content:
            report.issues.append(ValidationIssue("image_placeholders", "Missing image placeholders.", severity="warning"))

        return report
