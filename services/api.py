import requests

from config import API_URL, API_TOKEN


class ApiClient:

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Accept": "application/json",
        }

    def topic_exists(self, title: str) -> bool:
        response = requests.post(
            f"{API_URL}/automation/check-topic",
            headers=self.headers,
            json={
                "title": title,
            },
        )

        response.raise_for_status()

        return response.json()["exists"]

    def publish(self, article: dict, image_path: str):

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

            response = requests.post(
                f"{API_URL}/automation/publish",
                headers=self.headers,
                data=data,
                files=files,
            )

        response.raise_for_status()

        return response.json()