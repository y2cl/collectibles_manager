"""
Image Sources Configuration for Baseball Cards.
Adapted from the root image_sources.py — Streamlit and collectiman circular
imports replaced with direct access to backend config settings.
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import re


class ImageSource:
    def __init__(self, name: str, base_url: str, description: str):
        self.name = name
        self.base_url = base_url
        self.description = description
        self.enabled = True

    def search_image(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        raise NotImplementedError


class eBayImageSource(ImageSource):
    def __init__(self):
        super().__init__(
            name="eBay",
            base_url="https://svcs.ebay.com/services/search/FindingService/v1",
            description="eBay gallery images from card listings",
        )

    def search_image(self, player_name: str, year: str, set_name: str, card_number: str,
                     ebay_env: str = "Sandbox") -> str:
        try:
            from ..config import settings

            if ebay_env == "Production":
                ebay_app_id = settings.ebay_app_id
                base_url = "https://svcs.ebay.com/services/search/FindingService/v1"
            else:
                ebay_app_id = settings.ebay_app_id_sbx
                base_url = "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"

            if not ebay_app_id:
                return ""

            query_parts = [p for p in [player_name, year, set_name, f"#{card_number}" if card_number else ""] if p]
            if not query_parts:
                return ""

            params = {
                "OPERATION-NAME": "findItemsAdvanced",
                "SERVICE-VERSION": "1.0.0",
                "SECURITY-APPNAME": ebay_app_id,
                "RESPONSE-DATA-FORMAT": "JSON",
                "REST-PAYLOAD": "",
                "keywords": " ".join(query_parts),
                "categoryId": "212",
                "sortOrder": "BestMatch",
                "paginationInput.entriesPerPage": "3",
            }

            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            items = (
                data.get("findItemsAdvancedResponse", [{}])[0]
                .get("searchResult", [{}])[0]
                .get("item", [])
            )
            for item in items:
                gallery_url = item.get("galleryURL", [{}])[0]
                if gallery_url:
                    return gallery_url

            return ""
        except Exception as e:
            print(f"⚠️ eBayImageSource Error: {e}")
            return ""


class SportLotsImageSource(ImageSource):
    def __init__(self):
        super().__init__(
            name="SportLots",
            base_url="https://www.sportlots.com",
            description="SportLots card inventory images",
        )

    def search_image(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        try:
            query_parts = [p.replace(" ", "+") for p in [player_name, year, set_name] if p]
            if not query_parts:
                return ""
            search_url = f"{self.base_url}/inven/search?search={'+'.join(query_parts)}&sport=1"
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src", "")
                alt = img.get("alt", "").lower()
                if ("card" in src.lower() or "item" in src.lower()) and player_name.lower() in alt:
                    return (self.base_url + src) if src.startswith("/") else src
            return ""
        except Exception as e:
            print(f"⚠️ SportLotsImageSource Error: {e}")
            return ""


class SportCardsProImageSource(ImageSource):
    def __init__(self):
        super().__init__(
            name="SportCardsPro",
            base_url="https://www.sportscardspro.com",
            description="SportCardsPro card database images",
        )

    def search_image(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        try:
            search_query = f"{player_name} {year} {set_name}".replace(" ", "+")
            search_url = f"{self.base_url}/search?q={search_query}"
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src", "")
                alt = img.get("alt", "").lower()
                if player_name.lower() in alt and ("card" in src.lower() or "image" in src.lower()):
                    return (self.base_url + src) if src.startswith("/") else src
            return ""
        except Exception as e:
            print(f"⚠️ SportCardsProImageSource Error: {e}")
            return ""


class ImageSourceManager:
    def __init__(self):
        self.sources = [
            eBayImageSource(),
            SportCardsProImageSource(),
            SportLotsImageSource(),
        ]

    def search_all_sources(self, player_name: str, year: str, set_name: str,
                           card_number: str, ebay_env: str = "Sandbox") -> str:
        for source in self.sources:
            if not source.enabled:
                continue
            if isinstance(source, eBayImageSource):
                image_url = source.search_image(player_name, year, set_name, card_number, ebay_env)
            else:
                image_url = source.search_image(player_name, year, set_name, card_number)
            if image_url:
                return image_url
        return ""

    def get_source_status(self) -> Dict[str, Dict]:
        return {
            s.name: {"enabled": s.enabled, "description": s.description, "base_url": s.base_url}
            for s in self.sources
        }


image_manager = ImageSourceManager()


def find_baseball_card_image(player_name: str, year: str, set_name: str, card_number: str,
                              ebay_env: str = "Sandbox") -> str:
    return image_manager.search_all_sources(player_name, year, set_name, card_number, ebay_env)
