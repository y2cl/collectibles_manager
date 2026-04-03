"""
Image Sources Configuration for Baseball Cards
This module manages different sources for baseball card images
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import re
import urllib.parse

class ImageSource:
    """Base class for image sources"""
    def __init__(self, name: str, base_url: str, description: str):
        self.name = name
        self.base_url = base_url
        self.description = description
        self.enabled = True
    
    def search_image(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        """Search for card image - to be implemented by subclasses"""
        raise NotImplementedError

class eBayImageSource(ImageSource):
    """eBay image source using Finding API"""
    def __init__(self):
        super().__init__(
            name="eBay",
            base_url="https://svcs.ebay.com/services/search/FindingService/v1",
            description="eBay gallery images from card listings"
        )
    
    def search_image(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        """Search eBay for card images"""
        try:
            # Import here to avoid circular imports
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from collectiman import get_secret
            import streamlit as st
            
            # Check which eBay environment to use
            ebay_env = st.session_state.get("last_ebay_env", "Sandbox")
            
            if ebay_env == "Production":
                ebay_app_id = get_secret("EBAY_APP_ID")
                base_url = "https://svcs.ebay.com/services/search/FindingService/v1"
            else:
                ebay_app_id = get_secret("EBAY_APP_ID_SBX")
                base_url = "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"
            
            # Build search query
            query_parts = []
            if player_name:
                query_parts.append(player_name)
            if year:
                query_parts.append(year)
            if set_name:
                query_parts.append(set_name)
            if card_number:
                query_parts.append(f"#{card_number}")
            
            if not query_parts:
                return ""
            
            query = " ".join(query_parts)
            
            # Get eBay API credentials
            if not ebay_app_id:
                return ""
            
            # API parameters
            params = {
                "OPERATION-NAME": "findItemsAdvanced",
                "SERVICE-VERSION": "1.0.0",
                "SECURITY-APPNAME": ebay_app_id,
                "RESPONSE-DATA-FORMAT": "JSON",
                "REST-PAYLOAD": "",
                "keywords": query,
                "categoryId": "212",  # Baseball cards
                "itemFilter(0).name": "PictureURL",
                "itemFilter(0).value": "true",
                "sortOrder": "BestMatch",
                "paginationInput.entriesPerPage": "3"
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Parse response for image URLs
            items = data.get("findItemsAdvancedResponse", [{}])[0].get("searchResult", [{}])[0].get("item", [])
            
            for item in items:
                gallery_url = item.get("galleryURL", [{}])[0]
                if gallery_url:
                    print(f"🖼️ {self.name} ({ebay_env}): Found image - {gallery_url}")
                    return gallery_url
            
            return ""
            
        except Exception as e:
            print(f"⚠️ {self.name} Error: {e}")
            return ""

class SportLotsImageSource(ImageSource):
    """SportLots image source"""
    def __init__(self):
        super().__init__(
            name="SportLots",
            base_url="https://www.sportlots.com",
            description="SportLots card inventory images"
        )
    
    def search_image(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        """Search SportLots for card images"""
        try:
            # Build search query
            query_parts = []
            if player_name:
                query_parts.append(player_name.replace(" ", "+"))
            if year:
                query_parts.append(year)
            if set_name:
                query_parts.append(set_name.replace(" ", "+"))
            
            if not query_parts:
                return ""
            
            query = "+".join(query_parts)
            search_url = f"{self.base_url}/inven/search?search={query}&sport=1"
            
            print(f"🔍 {self.name}: Searching - {search_url}")
            
            response = requests.get(search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for card images - adapt to SportLots HTML structure
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                
                # Look for card-related images
                if ('card' in src.lower() or 'item' in src.lower()) and player_name.lower() in alt:
                    if src.startswith('/'):
                        src = self.base_url + src
                    print(f"🖼️ {self.name}: Found image - {src}")
                    return src
            
            return ""
            
        except Exception as e:
            print(f"⚠️ {self.name} Error: {e}")
            return ""

class ImageSourceManager:
    """Manager for multiple image sources"""
    def __init__(self):
        self.sources = [
            eBayImageSource(),
            SportLotsImageSource(),
        ]
    
    def search_all_sources(self, player_name: str, year: str, set_name: str, card_number: str) -> str:
        """Search all enabled sources for card image"""
        print(f"🖼️ Searching for image: {player_name} {year} {set_name} #{card_number}")
        
        for source in self.sources:
            if not source.enabled:
                continue
                
            print(f"🔍 Trying {source.name}...")
            image_url = source.search_image(player_name, year, set_name, card_number)
            
            if image_url and image_url != "":
                print(f"✅ {source.name}: SUCCESS - {image_url}")
                return image_url
            else:
                print(f"❌ {self.name}: No image found")
        
        print("❌ All sources failed - no image found")
        return ""
    
    def enable_source(self, source_name: str, enabled: bool = True):
        """Enable or disable a specific source"""
        for source in self.sources:
            if source.name == source_name:
                source.enabled = enabled
                print(f"🔧 {source_name}: {'Enabled' if enabled else 'Disabled'}")
                return True
        return False
    
    def get_source_status(self) -> Dict[str, Dict]:
        """Get status of all sources"""
        return {
            source.name: {
                "enabled": source.enabled,
                "description": source.description,
                "base_url": source.base_url
            }
            for source in self.sources
        }

# Global instance
image_manager = ImageSourceManager()

# Convenience function
def find_baseball_card_image(player_name: str, year: str, set_name: str, card_number: str) -> str:
    """Find baseball card image from all available sources"""
    return image_manager.search_all_sources(player_name, year, set_name, card_number)
