import time
import requests

from config import API_URL, API_TOKEN


class ApiClient:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {API_TOKEN}",
            "Accept": "application/json",
        })

    def topic_exists(self, title: str, max_retries: int = 3, backoff_seconds: int = 3) -> bool:
        url = f"{API_URL}/automation/check-topic"

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    json={"title": title},
                )
                response.raise_for_status()
                return response.json()["exists"]
            except requests.RequestException as e:
                if attempt == max_retries:
                    raise
                print(
                    f"Topic existence check attempt {attempt} failed: {e}. "
                    f"Retrying in {backoff_seconds * attempt} seconds..."
                )
                time.sleep(backoff_seconds * attempt)

    def publish(self, article: dict, image_path: str, max_retries: int = 3, backoff_seconds: int = 5):
        url = f"{API_URL}/automation/publish"
        response = None

        for attempt in range(1, max_retries + 1):
            try:
                with open(image_path, "rb") as image:
                    files = {
                        "featured_image": image,
                    }

                    data = {
                        "title": article["title"],
                        "slug": article.get("slug", ""),
                        "excerpt": article.get("excerpt", ""),
                        "content": article["content"],
                    }

                    if article.get("category_id"):
                        data["category_id"] = article["category_id"]

                    response = self.session.post(
                        url,
                        data=data,
                        files=files,
                    )

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                body = response.text if response is not None else None
                if attempt == max_retries:
                    print(f"Publish failed after {attempt} attempts: {e}")
                    if body:
                        print(f"Publish response body: {body}")
                    raise

                wait = backoff_seconds * attempt
                print(
                    f"Publish attempt {attempt} failed: {e}. "
                    f"Retrying in {wait} seconds..."
                )
                if body:
                    print(f"Last response body: {body}")
                time.sleep(wait)