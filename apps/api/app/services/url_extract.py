"""Extract product info from Shopee / TikTok Shop URLs.

Strategy:
- Shopee: Try API endpoint, fallback to HTML JSON-LD parsing
- TikTok: Try __INITIAL_STATE__ JSON in HTML
- No headless browser (too heavy for MVP)
- Return partial=True if extraction is incomplete
"""

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def detect_platform(url: str) -> str:
    if "shopee" in url.lower():
        return "shopee"
    if "tiktok" in url.lower():
        return "tiktok"
    return "unknown"


def _parse_shopee_ids(url: str) -> tuple[str | None, str | None]:
    """Extract shop_id and item_id from Shopee URL pattern: .../shop_id.item_id"""
    match = re.search(r"\.(\d+)\.(\d+)", url)
    if match:
        return match.group(1), match.group(2)
    # Try i.shop_id.item_id pattern
    match = re.search(r"i\.(\d+)\.(\d+)", url)
    if match:
        return match.group(1), match.group(2)
    return None, None


async def _extract_shopee(url: str) -> dict:
    result = {
        "name": None, "description": None, "price": None,
        "currency": "VND", "images": [], "category": None,
        "platform": "shopee", "partial": False,
    }

    shop_id, item_id = _parse_shopee_ids(url)
    if not shop_id or not item_id:
        result["partial"] = True
        return result

    # Try Shopee API
    api_url = f"https://shopee.vn/api/v4/item/get?shopid={shop_id}&itemid={item_id}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as client:
            resp = await client.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                item = data.get("data") or {}
                result["name"] = item.get("name")
                result["description"] = item.get("description")
                price_raw = item.get("price")
                if price_raw:
                    result["price"] = price_raw / 100000  # Shopee stores price * 100000
                images = item.get("images") or []
                result["images"] = [
                    f"https://cf.shopee.vn/file/{img}" for img in images[:10]
                ]
                cats = item.get("categories") or []
                if cats:
                    result["category"] = cats[-1].get("display_name")
                return result
    except Exception:
        logger.debug("Shopee API failed, trying HTML fallback")

    # Fallback: fetch HTML and look for JSON-LD
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            text = resp.text

            # Try JSON-LD
            ld_match = re.search(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                text, re.DOTALL,
            )
            if ld_match:
                ld = json.loads(ld_match.group(1))
                if isinstance(ld, list):
                    ld = ld[0]
                result["name"] = ld.get("name")
                result["description"] = ld.get("description")
                offers = ld.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0]
                price = offers.get("price")
                if price:
                    result["price"] = float(price)
                image = ld.get("image")
                if isinstance(image, list):
                    result["images"] = image[:10]
                elif image:
                    result["images"] = [image]
    except Exception:
        logger.debug("Shopee HTML parse failed")

    if not result["name"]:
        result["partial"] = True
    return result


async def _extract_tiktok(url: str) -> dict:
    result = {
        "name": None, "description": None, "price": None,
        "currency": "VND", "images": [], "category": None,
        "platform": "tiktok", "partial": False,
    }

    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            text = resp.text

            # Try __INITIAL_STATE__
            match = re.search(r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;?\s*</script>', text, re.DOTALL)
            if match:
                state = json.loads(match.group(1))
                product = state.get("product", {}).get("data", {})
                result["name"] = product.get("title")
                result["description"] = product.get("description")
                price_data = product.get("price", {})
                if price_data.get("original_price"):
                    result["price"] = float(price_data["original_price"])
                images = product.get("images", [])
                result["images"] = [
                    img.get("url") or img.get("thumb_url", "")
                    for img in images[:10]
                    if isinstance(img, dict)
                ]
                return result

            # Fallback: JSON-LD
            ld_match = re.search(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                text, re.DOTALL,
            )
            if ld_match:
                ld = json.loads(ld_match.group(1))
                if isinstance(ld, list):
                    ld = ld[0]
                result["name"] = ld.get("name")
                result["description"] = ld.get("description")
    except Exception:
        logger.debug("TikTok extraction failed")

    if not result["name"]:
        result["partial"] = True
    return result


_ALLOWED_DOMAINS = {"shopee.vn", "shopee.co.th", "shopee.sg", "tiktok.com", "www.tiktok.com"}


def _validate_url(url: str) -> bool:
    """Only allow known e-commerce domains (allowlist approach for SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
    return any(hostname == d or hostname.endswith(f".{d}") for d in _ALLOWED_DOMAINS)


async def extract_from_url(url: str) -> dict:
    if not _validate_url(url):
        return {
            "name": None, "description": None, "price": None,
            "currency": "VND", "images": [], "category": None,
            "platform": "unknown", "partial": True,
        }

    platform = detect_platform(url)
    if platform == "shopee":
        return await _extract_shopee(url)
    if platform == "tiktok":
        return await _extract_tiktok(url)

    # Unknown platform
    return {
        "name": None, "description": None, "price": None,
        "currency": "VND", "images": [], "category": None,
        "platform": "unknown", "partial": True,
    }
