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
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

_GOOGLEBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept-Language": "vi-VN,vi;q=0.9",
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


def _name_from_slug(url: str) -> str | None:
    """Extract product name from Shopee URL slug as last resort."""
    from urllib.parse import urlparse, unquote
    path = unquote(urlparse(url).path)
    slug = path.split("/")[-1]
    slug = slug.rsplit("-i.", 1)[0] if "-i." in slug else slug
    name = slug.replace("-", " ").strip()
    return name if len(name) > 3 else None


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

    # Try Shopee API first (may be blocked)
    api_url = f"https://shopee.vn/api/v4/item/get?shopid={shop_id}&itemid={item_id}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as client:
            resp = await client.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                item = data.get("data") or {}
                if item.get("name"):
                    result["name"] = item["name"]
                    result["description"] = item.get("description")
                    price_raw = item.get("price")
                    if price_raw:
                        result["price"] = price_raw / 100000
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

    # Fallback: fetch HTML with Googlebot UA (Shopee serves OG meta tags to bots)
    try:
        async with httpx.AsyncClient(
            headers=_GOOGLEBOT_HEADERS, timeout=15, follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            text = resp.text

            # Parse OG meta tags — flexible regex to handle extra attrs
            # like data-rh="true" that Shopee injects before content/property
            og_meta = {}
            for m in re.finditer(r"<meta\s+[^>]*?(?:property|name)=\"([^\"]+)\"[^>]*?content=\"([^\"]*)\"", text):
                og_meta[m.group(1)] = m.group(2)
            for m in re.finditer(r"<meta\s+[^>]*?content=\"([^\"]*)\"[^>]*?(?:property|name)=\"([^\"]+)\"", text):
                og_meta.setdefault(m.group(2), m.group(1))

            og_title = og_meta.get("og:title", "")
            if og_title:
                # Remove " | Shopee Việt Nam" suffix
                result["name"] = re.sub(r"\s*\|\s*Shopee.*$", "", og_title).strip()

            og_desc = og_meta.get("og:description") or og_meta.get("description", "")
            if og_desc:
                result["description"] = og_desc.strip()

            og_image = og_meta.get("og:image", "")
            if og_image:
                result["images"] = [og_image]

            # Try to find price in page content
            price_match = re.search(r'"price"[:\s]+"?([\d,.]+)"?', text)
            if price_match:
                try:
                    result["price"] = float(price_match.group(1).replace(",", ""))
                except ValueError:
                    pass

            # Try JSON-LD as additional source
            ld_match = re.search(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                text, re.DOTALL,
            )
            if ld_match:
                try:
                    ld = json.loads(ld_match.group(1))
                    if isinstance(ld, list):
                        ld = ld[0]
                    if not result["name"] and ld.get("name"):
                        result["name"] = ld["name"]
                    if not result["description"] and ld.get("description"):
                        result["description"] = ld["description"]
                    offers = ld.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0]
                    if not result["price"] and offers.get("price"):
                        result["price"] = float(offers["price"])
                except (json.JSONDecodeError, ValueError):
                    pass
    except Exception:
        logger.debug("Shopee HTML parse failed")

    # Last resort: extract name from URL slug
    if not result["name"]:
        result["name"] = _name_from_slug(url)

    if not result["name"]:
        result["partial"] = True
    return result


def _name_from_tiktok_slug(url: str) -> str | None:
    """Extract product name from TikTok Shop PDP URL slug."""
    from urllib.parse import urlparse, unquote
    path = unquote(urlparse(url).path)
    # /shop/vn/pdp/{slug}/{product_id}
    m = re.search(r"/pdp/([^/]+)/\d+", path)
    if m:
        name = m.group(1).replace("-", " ").strip()
        return name if len(name) > 3 else None
    return None


def _parse_tiktok_price(html: str) -> float | None:
    """Extract product price from TikTok Shop inline script data."""
    # TikTok embeds product data in large script tags with price fields like:
    #   "sale_price_decimal":"503960" (= 503,960 VND)
    #   "origin_price_decimal":"857000" (= 857,000 VND)
    m = re.search(r'"sale_price_decimal"\s*:\s*"(\d+)"', html)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    m = re.search(r'"origin_price_decimal"\s*:\s*"(\d+)"', html)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


async def _extract_tiktok(url: str) -> dict:
    from urllib.parse import urlparse, parse_qs

    result = {
        "name": None, "description": None, "price": None,
        "currency": "VND", "images": [], "category": None,
        "platform": "tiktok", "partial": False,
    }

    # TikTok share links embed product info in og_info query param
    parsed = urlparse(url)
    og_raw = parse_qs(parsed.query).get("og_info", [None])[0]
    if og_raw:
        try:
            og = json.loads(og_raw)
            result["name"] = og.get("title")
            image = og.get("image")
            if image:
                result["images"] = [image]
        except (json.JSONDecodeError, ValueError):
            pass

    # Try fetching the page for additional data (price, description)
    # TikTok requires cookies (ttwid) — first request sets them, second gets full HTML
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            if "og:title" not in resp.text and "sale_price" not in resp.text:
                resp = await client.get(url)
            text = resp.text

            # Parse OG meta tags
            og_meta = {}
            for m in re.finditer(r"<meta\s+[^>]*?(?:property|name)=\"([^\"]+)\"[^>]*?content=\"([^\"]*)\"", text):
                og_meta[m.group(1)] = m.group(2)
            for m in re.finditer(r"<meta\s+[^>]*?content=\"([^\"]*)\"[^>]*?(?:property|name)=\"([^\"]+)\"", text):
                og_meta.setdefault(m.group(2), m.group(1))

            if not result["name"] and og_meta.get("og:title"):
                result["name"] = og_meta["og:title"]
            if not result["description"]:
                desc = og_meta.get("og:description") or og_meta.get("description")
                if desc:
                    result["description"] = desc
            if not result["images"] and og_meta.get("og:image"):
                result["images"] = [og_meta["og:image"]]

            # Extract price from inline script data
            if not result["price"]:
                result["price"] = _parse_tiktok_price(text)

            # Try __INITIAL_STATE__
            match = re.search(r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;?\s*</script>', text, re.DOTALL)
            if match:
                try:
                    state = json.loads(match.group(1))
                    product = state.get("product", {}).get("data", {})
                    if not result["name"] and product.get("title"):
                        result["name"] = product["title"]
                    if not result["description"] and product.get("description"):
                        result["description"] = product["description"]
                    price_data = product.get("price", {})
                    if not result["price"] and price_data.get("original_price"):
                        result["price"] = float(price_data["original_price"])
                    if not result["images"]:
                        images = product.get("images", [])
                        result["images"] = [
                            img.get("url") or img.get("thumb_url", "")
                            for img in images[:10]
                            if isinstance(img, dict)
                        ]
                except (json.JSONDecodeError, ValueError):
                    pass

            # Fallback: JSON-LD
            if not result["name"]:
                ld_match = re.search(
                    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                    text, re.DOTALL,
                )
                if ld_match:
                    try:
                        ld = json.loads(ld_match.group(1))
                        if isinstance(ld, list):
                            ld = ld[0]
                        if not result["name"]:
                            result["name"] = ld.get("name")
                        if not result["description"]:
                            result["description"] = ld.get("description")
                    except (json.JSONDecodeError, ValueError):
                        pass
    except Exception:
        logger.debug("TikTok HTML fetch failed")

    # Last resort: extract name from URL slug
    if not result["name"]:
        result["name"] = _name_from_tiktok_slug(url)

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
