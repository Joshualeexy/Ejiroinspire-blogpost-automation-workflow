import json
import os
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List

from services.ollama_client import OllamaClient


class TopicGenerator:
    # Python owns diversity. Category -> list of concrete product families.
    # The LLM never sees this whole structure — only the one category/product
    # we already picked for it.
    CATEGORIES: Dict[str, List[str]] = {
        # -- Tech / gadgets --------------------------------------------------
        "Smartphones": ["Budget Android Phones", "Foldable Phones", "Camera Phones", "Rugged Phones"],
        "Laptops": ["Ultrabooks", "Gaming Laptops", "2-in-1 Convertibles", "Chromebooks"],
        "Monitors": ["Ultrawide Monitors", "4K Monitors", "Portable Monitors", "Curved Gaming Monitors"],
        "PC Components": ["Graphics Cards", "Power Supplies", "CPU Coolers", "PC Cases"],
        "Mechanical Keyboards": ["Hot-Swappable Keyboards", "Compact 60% Keyboards", "Wireless Mechanical Keyboards"],
        "Gaming Mice": ["Wireless Gaming Mice", "Lightweight Gaming Mice", "Ergonomic Gaming Mice"],
        "Webcams": ["4K Webcams", "Streaming Webcams", "Budget Webcams"],
        "Microphones": ["USB Streaming Mics", "XLR Podcast Mics", "Lavalier Mics"],
        "Headphones": ["Noise Cancelling Headphones", "Open-Back Headphones", "Gaming Headsets"],
        "Earbuds": ["True Wireless Earbuds", "Sport Earbuds", "Budget Earbuds"],
        "Bluetooth Speakers": ["Portable Bluetooth Speakers", "Waterproof Speakers", "Party Speakers"],
        "TVs": ["Budget 4K TVs", "OLED TVs", "Mini-LED TVs"],
        "Projectors": ["Home Theater Projectors", "Portable Projectors", "Short-Throw Projectors"],
        "Streaming Devices": ["Streaming Sticks", "Streaming Boxes", "Media Servers"],
        "Networking": ["WiFi Routers", "Mesh WiFi Systems", "Network Switches", "Access Points"],
        "NAS": ["Home NAS Devices", "Small Business NAS", "NAS Hard Drives"],
        "Printers": ["Home Office Printers", "Photo Printers", "Label Printers"],
        "Smart Home": ["Smart Plugs", "Smart Thermostats", "Smart Lighting Kits"],
        "Home Security": ["Security Cameras", "Video Doorbells", "Smart Locks"],
        "Wearables": ["Fitness Trackers", "Smartwatches", "Sleep Trackers"],
        "Web Services": ["Web Hosting Plans", "VPN Services", "Domain Registrars"],
        "Digital Security": ["Password Managers", "Antivirus Software", "Cloud Backup Services"],
        "Creative Software": ["Video Editing Software", "Photo Editing Software", "Screen Recording Software"],
        "Productivity Software": ["Note-Taking Apps", "Project Management Tools", "Email Marketing Software"],
        "AI Tools": ["AI Writing Assistants", "AI Image Generators", "AI Transcription Tools"],
        "Musical Gear": ["Audio Interfaces", "MIDI Keyboards", "Studio Monitors"],

        # -- Home / kitchen ---------------------------------------------------
        "Office Furniture": ["Ergonomic Office Chairs", "Standing Desks", "Monitor Arms"],
        "Coffee": ["Espresso Machines", "Drip Coffee Makers", "Coffee Grinders", "Pod Coffee Machines"],
        "Kitchen Appliances": ["Air Fryers", "Blenders", "Stand Mixers", "Toaster Ovens"],
        "Home Cleaning": ["Robot Vacuums", "Cordless Vacuums", "Steam Mops"],
        "Home & Garden": ["Raised Garden Beds", "Indoor Plant Kits", "Patio Furniture", "Grills"],

        # -- Personal care / wearable ------------------------------------------
        "Recovery Tools": ["Massage Guns", "Foam Rollers", "Compression Boots"],
        "Personal Care": ["Electric Toothbrushes", "Hair Dryers", "Electric Shavers"],
        "Baby Tech": ["Baby Monitors", "Smart Baby Scales", "White Noise Machines"],

        # -- Outdoors / travel / auto -------------------------------------------
        "Car Accessories": ["Dash Cams", "Jump Starters", "Car Phone Mounts"],
        "Outdoor Gear": ["Roof Cargo Boxes", "Camping Tents", "Hiking Backpacks", "Camping Stoves"],
        "Cycling": ["Indoor Bike Trainers", "Bike Computers", "Commuter Bikes"],
        "Travel": ["Carry-On Luggage", "Travel Backpacks", "Packing Cubes", "Portable Chargers for Travel"],
        "Solo & Group Travel": ["Solo Travel Planning", "Group Trip Itineraries", "Budget Travel Destinations"],

        # -- Money / career -------------------------------------------------
        "Personal Finance": ["Budgeting Apps", "High-Yield Savings Accounts", "Investing Apps for Beginners"],
        "Saving Money": ["Meal Planning to Save Money", "Cash-Back Apps", "Subscription Audit Tools"],
        "Remote Work": ["Home Office Setups for Remote Work", "Remote Team Collaboration Tools", "Coworking Alternatives"],
        "Career & Productivity": ["Resume Builder Tools", "Time-Tracking Apps", "Freelance Invoicing Software"],

        # -- Food / health / lifestyle ---------------------------------------
        "Food & Nutrition": ["Meal Kit Delivery Services", "Healthy Snack Subscription Boxes", "Meal Prep Containers"],
        "Fitness & Wellness": ["Home Gym Equipment", "Yoga Mats", "Resistance Bands"],
        "Minimalism & Lifestyle": ["Minimalist Home Organization", "Capsule Wardrobe Essentials", "Decluttering Tools"],
        "Productivity & Habits": ["Habit Tracking Apps", "Planner and Journal Systems", "Focus and Deep Work Tools"],

        # -- Family / pets / learning -----------------------------------------
        "Pets": ["Automatic Pet Feeders", "Dog GPS Trackers", "Pet Grooming Kits"],
        "Education & Learning": ["Online Course Platforms", "Language Learning Apps", "Kids' Educational Tablets"],
    }

    FORMATS = [
        "Review",
        "Comparison",
        "Buying Guide",
        "Best Product List",
        "Best Product Under Budget",
        "Alternatives",
        "Pros and Cons",
        "Is It Worth It",
    ]

    VALID_TYPES = {f.lower() for f in FORMATS}

    # How many of the most recent posts' categories to exclude when picking
    # the next one, so you can't get a run of same/adjacent-feeling topics
    # (e.g. Networking -> Home Security -> Smart Home back to back).
    RECENT_CATEGORY_WINDOW = 5

    def __init__(
        self,
        model_name: str | None = None,
        max_retries: int = 3,
        history_file: str = "generated_topics.json",
        history_limit: int = 1000,
    ):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.max_retries = max_retries
        self.history_file = history_file
        self.history_limit = history_limit
        self.client = OllamaClient(self.model_name)

    # -- history / dedup -------------------------------------------------

    def _load_history(self) -> List[Dict[str, str]]:
        """Each entry: {"title": ..., "category": ...}. Tolerates the older
        plain-string format from before category tracking was added."""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, list):
            return []

        normalized = []
        for entry in data:
            if isinstance(entry, dict) and "title" in entry:
                normalized.append({"title": entry["title"], "category": entry.get("category", "")})
            elif isinstance(entry, str):
                normalized.append({"title": entry, "category": ""})
        return normalized

    def _save_history(self, history: List[Dict[str, str]]) -> None:
        trimmed = history[-self.history_limit:]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, indent=2)

    def _is_duplicate(self, title: str, history: List[Dict[str, str]]) -> bool:
        normalized = title.strip().lower()
        return any(normalized == entry["title"].strip().lower() for entry in history)

    # Matches a standalone 4-digit year like 2024, 2026, 2031 -- not part of
    # a longer number (e.g. won't match the "2024" inside "SM-2024X").
    YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

    def _year_violation(self, title: str, article_type: str) -> str | None:
        """Prompt instructions alone don't reliably stop the model from
        appending stale SEO-pattern years like 'for 2024' -- this is common
        training-data noise the model reaches for regardless of what the
        prompt says. Enforce the year rule in code instead of trusting it."""
        match = self.YEAR_PATTERN.search(title)
        if not match:
            return None

        found_year = match.group(1)
        current_year = str(datetime.now().year)

        if article_type.lower() == "best product list":
            if found_year != current_year:
                return f"Stale year '{found_year}' in title (current year is {current_year})"
            return None

        return f"Year '{found_year}' not allowed in a {article_type} title"

    # Common ways a year shows up as removable filler, vs. being genuinely
    # part of the title (e.g. a named model year comparison, which we leave
    # alone -- see _strip_disallowed_year).
    YEAR_STRIP_PATTERNS = [
        re.compile(r"\s*[\(\[]\s*20\d{2}\s*[\)\]]"),        # "(2026)" / "[2026]"
        re.compile(r"\s*[-:–]\s*20\d{2}\s*$"),                # trailing "- 2026" / ": 2026"
        re.compile(r"\s+for\s+20\d{2}\b", re.IGNORECASE),     # "... for 2026"
        re.compile(r"\s+in\s+20\d{2}\b", re.IGNORECASE),      # "... in 2026"
        re.compile(r"\s+20\d{2}\s+(edition|guide|update)\b", re.IGNORECASE),
    ]

    def _strip_disallowed_year(self, title: str) -> str | None:
        """Best-effort auto-fix for a title that failed the year check.
        Returns the cleaned title, or None if the year couldn't be safely
        removed (e.g. it's woven into the title in a way that isn't a known
        filler pattern) -- caller falls back to rejecting/retrying in that
        case rather than mangling the title."""
        cleaned = title
        for pattern in self.YEAR_STRIP_PATTERNS:
            cleaned = pattern.sub("", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -:–")

        if self.YEAR_PATTERN.search(cleaned):
            return None
        return cleaned

    def _pick_category(self, history: List[Dict[str, str]]) -> str:
        recent = {
            entry["category"]
            for entry in history[-self.RECENT_CATEGORY_WINDOW:]
            if entry.get("category")
        }
        candidates = [c for c in self.CATEGORIES if c not in recent]
        # If somehow everything is excluded (tiny category list, huge window),
        # fall back to the full list rather than crashing.
        if not candidates:
            candidates = list(self.CATEGORIES.keys())
        return random.choice(candidates)

    # -- prompt -----------------------------------------------------------

    def _build_prompt(self, category: str, product: str, article_type: str) -> str:
        current_year = datetime.now().year

        # Only surface the actual year number when this format is allowed to
        # use it. Printing "{current_year}" into every prompt -- even ones
        # instructing the model NOT to use a year -- gave the model a fresh
        # number to latch onto and it started appending it anyway. Simplest
        # fix: don't put the number in front of the model unless it's needed.
        if article_type.lower() == "best product list":
            year_instructions = f"""
The current year is {current_year}. You may include {current_year} in the
title only if it is genuinely necessary -- never an earlier year."""
        else:
            year_instructions = """
Do not include any year anywhere in the title, in any form (not "for", "in",
parentheses, or as a suffix), unless comparing specific named model years
(e.g. "iPhone 15 vs iPhone 16")."""

        return f"""You are an SEO strategist for Ejiro Inspire.

Today's category: {category}
Focus on: {product}
Article format: {article_type}

Generate ONE original affiliate article idea for this category, product family,
and format. Prefer lesser-known brands over Apple, Dell, HP, Samsung. Mix
premium, mid-range, and budget options where relevant. Avoid crypto, gambling,
politics, celebrities, entertainment, medical, and legal topics.
{year_instructions}

Return ONLY valid JSON in this exact shape:

{{
    "type": "{article_type}",
    "title": "",
    "category": "{category}",
    "primary_keyword": "",
    "secondary_keywords": ["", "", ""]
}}"""

    # -- generation ---------------------------------------------------------

    def generate(self) -> Dict[str, Any]:
        history = self._load_history()

        category = self._pick_category(history)
        product = random.choice(self.CATEGORIES[category])
        article_type = random.choice(self.FORMATS)

        prompt = self._build_prompt(category, product, article_type)

        for attempt in range(self.max_retries):
            try:
                response = self.client.generate(
                    prompt=prompt,
                    format="json",
                    options={
                        "temperature": 1.0,
                        "top_p": 0.95,
                        "repeat_penalty": 1.2,
                    },
                )

                topic = json.loads(response["response"])

                required = ["type", "title", "category", "primary_keyword", "secondary_keywords"]
                for field in required:
                    if field not in topic:
                        raise ValueError(f"Missing field: {field}")

                for field in ["type", "title", "category", "primary_keyword"]:
                    if not isinstance(topic[field], str) or not topic[field].strip():
                        raise ValueError(f"Invalid {field}")

                if not isinstance(topic["secondary_keywords"], list):
                    raise ValueError("secondary_keywords must be a list")

                if len(topic["secondary_keywords"]) < 3:
                    raise ValueError("Need at least 3 secondary keywords")

                if not all(isinstance(x, str) and x.strip() for x in topic["secondary_keywords"]):
                    raise ValueError("Invalid secondary keywords")

                returned_type = topic["type"].strip().lower()
                if returned_type not in self.VALID_TYPES:
                    raise ValueError(f"Invalid article type: {returned_type}")

                if returned_type != article_type.lower():
                    raise ValueError(
                        f"Type mismatch: expected {article_type}, got {topic['type']}"
                    )

                year_issue = self._year_violation(topic["title"], article_type)
                if year_issue:
                    # "Best Product List" with a wrong year is a factual
                    # error (stale year), not just unwanted filler -- don't
                    # try to patch that, just regenerate.
                    if article_type.lower() == "best product list":
                        raise ValueError(year_issue)

                    fixed_title = self._strip_disallowed_year(topic["title"])
                    if fixed_title:
                        print(f"Auto-fixed title year: '{topic['title']}' -> '{fixed_title}'")
                        topic["title"] = fixed_title
                    else:
                        raise ValueError(year_issue)

                if self._is_duplicate(topic["title"], history):
                    raise ValueError(f"Duplicate title: {topic['title']}")

                history.append({"title": topic["title"].strip(), "category": category})
                self._save_history(history)

                return topic

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                print(f"Retry {attempt + 1}: {e}")
                time.sleep(1)