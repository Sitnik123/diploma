import os
import json
import hashlib
import requests
from datetime import datetime
from urllib.parse import urlparse

class ImageUploader:
    """Helper class to upload images to Imgur or ImgBB to get a public URL for Apify"""
    def __init__(self):
        self.imgur_client_id = os.getenv('IMGUR_CLIENT_ID')
        self.imgbb_api_key = os.getenv('IMGBB_API_KEY')

    def upload_to_imgur(self, image_path):
        if not self.imgur_client_id:
            return None
        try:
            url = "https://api.imgur.com/3/image"
            headers = {"Authorization": f"Client-ID {self.imgur_client_id}"}
            with open(image_path, "rb") as file:
                payload = {"image": file.read()}
                response = requests.post(url, headers=headers, data=payload)
                if response.status_code == 200:
                    return response.json()["data"]["link"]
        except Exception as e:
            print(f"[ERROR] Imgur upload failed: {e}")
        return None

    def upload_to_imgbb(self, image_path):
        if not self.imgbb_api_key:
            return None
        try:
            url = "https://api.imgbb.com/1/upload"
            with open(image_path, "rb") as file:
                payload = {
                    "key": self.imgbb_api_key,
                    "image": file.read(),
                }
                response = requests.post(url, data=payload)
                if response.status_code == 200:
                    return response.json()["data"]["url"]
        except Exception as e:
            print(f"[ERROR] ImgBB upload failed: {e}")
        return None

    def get_public_url(self, image_path):
        # Try Imgur first
        url = self.upload_to_imgur(image_path)
        if url: return url
        
        # Try ImgBB second
        url = self.upload_to_imgbb(image_path)
        return url

class ApifyReverseImageSearch:
    """Uses Apify actors for real reverse image search"""
    def __init__(self, token):
        self.token = token
        self.client = None
        if self.token:
            try:
                from apify_client import ApifyClient
                self.client = ApifyClient(self.token)
            except ImportError:
                print("[ERROR] apify-client not installed")

    def _extract_domain(self, url):
        try:
            domain = urlparse(url).netloc.replace('www.', '')
            return domain if domain else 'unknown'
        except:
            return 'unknown'

    def search_by_image_url(self, image_url):
        if not self.client: return []
        try:
            run_input = {"imageUrl": image_url, "mode": "visual_matches", "language": "ru"}
            run = self.client.actor("zen-studio/google-lens-visual-search").call(run_input=run_input)
            results = []
            for item in self.client.dataset(run['defaultDatasetId']).iterate_items():
                if 'visualMatches' in item:
                    for match in item['visualMatches']:
                        url = match.get('link') or match.get('url')
                        if url and url.startswith('http'):
                            results.append({
                                'url': url,
                                'title': match.get('title', 'Похожее изображение'),
                                'source': self._extract_domain(url),
                                'type': 'visual_match'
                            })
                if 'pagesWithImage' in item:
                    for page in item['pagesWithImage']:
                        url = page.get('link') or page.get('url')
                        if url and url.startswith('http'):
                            results.append({
                                'url': url,
                                'title': page.get('title', 'Страница с изображением'),
                                'source': self._extract_domain(url),
                                'type': 'page_with_image'
                            })
            return results[:15]
        except Exception as e:
            print(f"[ERROR] Apify Google Lens failed: {e}")
            return []

    def search_by_name(self, name):
        if not self.client: return []
        try:
            run_input = {"queries": name, "resultsPerPage": 20, "maxPagesPerQuery": 1, "searchType": "organic"}
            run = self.client.actor("apify/google-search-scraper").call(run_input=run_input)
            results = []
            for item in self.client.dataset(run['defaultDatasetId']).iterate_items():
                url = item.get('url')
                if url and url.startswith('http'):
                    results.append({
                        'url': url,
                        'title': item.get('title', 'Результат поиска'),
                        'snippet': item.get('description', ''),
                        'source': self._extract_domain(url),
                        'type': 'web_search'
                    })
            return results[:15]
        except Exception as e:
            print(f"[ERROR] Apify Google Search failed: {e}")
            return []

class SearchEngine:
    """Main engine for searching similar photos and web mentions"""
    def __init__(self):
        self.apify_token = os.getenv('APIFY_TOKEN')
        self.cache_file = 'Search_cache.json'
        self.cache = self._load_cache()
        self.uploader = ImageUploader()
        self.reverse_searcher = ApifyReverseImageSearch(self.apify_token)

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _get_cache_key(self, prefix, value):
        return hashlib.md5(f"{prefix}_{value}".lower().strip().encode()).hexdigest()

    def search_by_name(self, name):
        if not name or name == 'Неизвестный': return []
        cache_key = self._get_cache_key("name", name)
        if cache_key in self.cache:
            return self.cache[cache_key]['results']
        
        results = self.reverse_searcher.search_by_name(name)
        if results:
            self.cache[cache_key] = {'timestamp': datetime.now().timestamp(), 'results': results}
            self._save_cache()
        return results

    def search_images(self, name, local_path=None):
        cache_key = self._get_cache_key("image", f"{name}_{local_path}")
        if cache_key in self.cache:
            return self.cache[cache_key]['results']

        results = []
        if local_path and os.path.exists(local_path):
            public_url = self.uploader.get_public_url(local_path)
            if public_url:
                results = self.reverse_searcher.search_by_image_url(public_url)
        
        if not results and name and name != 'Неизвестный':
            results = self.search_by_name(name) # Fallback to name search if image search fails
            
        if results:
            self.cache[cache_key] = {'timestamp': datetime.now().timestamp(), 'results': results}
            self._save_cache()
        return results

    def get_statistics(self, results):
        sources = [res.get('source') for res in results if res.get('source')]
        return {
            'count': len(results),
            'unique_domains': len(set(sources)),
            'sources': list(set(sources))
        }
