import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://www.apple.com/shop/retail/pickup-message"

PRODUCTS = {
    "Black 256GB": "MJW44LL/A",
    "Black 512GB": "MJW84LL/A",
    "Black 1TB": "MJWD4LL/A",
    "Black 2TB": "MJWH4LL/A",
    "Burgundy 256GB": "MJW64LL/A",
    "Burgundy 512GB": "MJWA4LL/A",
    "Burgundy 1TB": "MJWF4LL/A",
    "Burgundy 2TB": "MJWK4LL/A",
}

PRODUCT_URLS = {
    "Black 256GB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-black",
    "Black 512GB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-512gb-black",
    "Black 1TB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-1tb-black",
    "Black 2TB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-2tb-black",
    "Burgundy 256GB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy",
    "Burgundy 512GB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-512gb-burgundy",
    "Burgundy 1TB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-1tb-burgundy",
    "Burgundy 2TB": "https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-2tb-burgundy",
}


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def parse_selected_products():
    raw = env("PRODUCTS_TO_MONITOR", "Black 256GB,Burgundy 256GB")
    selected = [x.strip() for x in raw.split(",") if x.strip()]
    unknown = [x for x in selected if x not in PRODUCTS]
    if unknown:
        raise ValueError(f"Unknown product name(s): {unknown}")
    if not selected:
        raise ValueError("No products selected.")
    return selected


def fetch_products(zip_code: str, selected_products, timeout: int = 25):
    params = {"location": zip_code, "pl": "true"}
    part_to_product = {}

    for index, product_name in enumerate(selected_products):
        part_number = PRODUCTS[product_name]
        params[f"parts.{index}"] = part_number
        part_to_product[part_number] = product_name

    url = ENDPOINT + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.apple.com/",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    head_status = str(payload.get("head", {}).get("status", ""))
    if head_status and head_status != "200":
        raise RuntimeError(f"Apple returned status {head_status}")

    stores = payload.get("body", {}).get("stores", [])

    if not stores:
        return {
            "query_status": "unavailable",
            "stores": [],
            "raw_message": "Apple returned no store-level pickup data.",
        }

    results = []

    for store in stores:
        parts_availability = store.get("partsAvailability", {})
        product_data = {}

        for part_number, product_name in part_to_product.items():
            availability = parts_availability.get(part_number, {})
            product_data[product_name] = {
                "part_number": part_number,
                "status": availability.get("pickupDisplay", "unknown"),
                "quote": availability.get("pickupSearchQuote", "No pickup message"),
            }

        results.append({
            "store_number": store.get("storeNumber") or "",
            "store_name": store.get("storeName") or "",
            "city": store.get("city") or "",
            "state": store.get("state") or "",
            "distance": store.get("storeDistanceWithUnit") or "",
            "products": product_data,
        })

    return {
        "query_status": "ok",
        "stores": results,
        "raw_message": "",
    }


def post_discord(webhook_url: str, payload: dict, timeout: int = 15):
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK is empty.")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AppleStockMonitor-GitHubActions/3.0",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"Discord returned HTTP {response.status}")


def build_discord_payload(zip_code, selected, result, errors):
    now_iso = datetime.now(timezone.utc).isoformat()

    if result["query_status"] != "ok":
        fields = [
            {
                "name": f"{product_name} ({PRODUCTS[product_name]})",
                "value": (
                    "⚠️ Availability lookup unavailable\n"
                    "Apple is not currently returning store-level pickup data."
                ),
                "inline": False,
            }
            for product_name in selected
        ]

        if errors:
            fields.append({
                "name": "Errors",
                "value": "\n".join(errors)[:1000],
                "inline": False,
            })

        return {
            "username": "Apple Stock Monitor",
            "content": "⚠️ Apple pickup availability lookup is currently unavailable.",
            "embeds": [{
                "title": "⚠️ Apple Pickup Availability Unavailable",
                "description": (
                    f"Apple is not currently returning store-level pickup data "
                    f"near ZIP **{zip_code}**.\n\n"
                    "This does **not** mean the products are out of stock."
                ),
                "color": 0xF1C40F,
                "fields": fields[:25],
                "timestamp": now_iso,
                "footer": {"text": "GitHub Actions Apple Stock Monitor"},
            }],
        }

    stores = result["stores"]
    available_items = []

    for product_name in selected:
        for store in stores:
            info = store["products"].get(product_name, {})
            if info.get("status") == "available":
                available_items.append((product_name, store, info))

    if available_items:
        content = "@everyone 🚨 **APPLE STOCK AVAILABLE**"
        title = "🚨 IN STOCK — Apple Pickup Available"
        description = (
            f"Found **{len(available_items)} available pickup option(s)** "
            f"near ZIP **{zip_code}**."
        )
        color = 0xE74C3C
    else:
        content = "🔎 Apple stock check completed."
        title = "Apple Stock Check — No Availability"
        description = (
            f"No selected model is currently available near ZIP **{zip_code}**."
        )
        color = 0x7F8C8D

    fields = []

    for product_name in selected:
        available_for_product = []

        for store in stores:
            info = store["products"].get(product_name, {})
            if info.get("status") == "available":
                available_for_product.append((store, info))

        if available_for_product:
            lines = []
            for store, info in available_for_product[:8]:
                lines.append(
                    f"✅ **{store.get('store_name', 'Unknown')}** — "
                    f"{info.get('quote', 'Available')} "
                    f"({store.get('distance', '')})"
                )

            buy_url = PRODUCT_URLS.get(
                product_name,
                "https://www.apple.com/shop/buy-iphone"
            )
            lines.append("")
            lines.append(f"[🛒 Open Apple Buy Page]({buy_url})")
            value = "\n".join(lines)
        else:
            value = "❌ No pickup availability"

        fields.append({
            "name": f"{product_name} ({PRODUCTS[product_name]})",
            "value": value,
            "inline": False,
        })

    if errors:
        fields.append({
            "name": "Errors",
            "value": "\n".join(errors)[:1000],
            "inline": False,
        })

    return {
        "username": "Apple Stock Monitor",
        "content": content,
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields[:25],
            "timestamp": now_iso,
            "footer": {"text": "GitHub Actions Apple Stock Monitor"},
        }],
    }


def main():
    zip_code = env("ZIP_CODE", "03079")
    webhook = env("DISCORD_WEBHOOK")
    selected = parse_selected_products()

    if not zip_code.isdigit() or len(zip_code) != 5:
        raise ValueError("ZIP_CODE must be a 5-digit ZIP code.")

    print(f"Checking ZIP {zip_code}")
    print("Products:", ", ".join(selected))

    errors = []

    try:
        result = fetch_products(zip_code, selected)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print("ERROR:", error)
        errors.append(error)
        result = {
            "query_status": "unavailable",
            "stores": [],
            "raw_message": error,
        }

    if result["query_status"] == "ok":
        print(f"Apple returned {len(result['stores'])} stores.")

        for product_name in selected:
            count = 0
            for store in result["stores"]:
                info = store["products"].get(product_name, {})
                if info.get("status") == "available":
                    count += 1
            print(f"{product_name}: {count} available store(s).")
    else:
        print("Apple did not return store-level pickup data.")

    payload = build_discord_payload(
        zip_code,
        selected,
        result,
        errors,
    )

    post_discord(webhook, payload)
    print("Discord summary sent.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
