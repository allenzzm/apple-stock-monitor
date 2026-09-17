import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://www.apple.com/shop/retail/pickup-message"

PRODUCTS = {
    "Black 256GB": "MJW44LL/A",
    "Black 512GB": "MJW84LL/A",
    "Black 1TB":   "MJWD4LL/A",
    "Black 2TB":   "MJWH4LL/A",
    "Burgundy 256GB": "MJW64LL/A",
    "Burgundy 512GB": "MJWA4LL/A",
    "Burgundy 1TB":   "MJWF4LL/A",
    "Burgundy 2TB":   "MJWK4LL/A",
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


def fetch_product(zip_code: str, part_number: str, timeout: int = 20):
    params = {
        "location": zip_code,
        "parts.0": part_number,
        "pl": "true",
    }
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
        raise RuntimeError("Apple returned no stores for this ZIP/SKU.")

    results = []
    for store in stores:
        availability = store.get("partsAvailability", {}).get(part_number, {})
        results.append({
            "store_number": store.get("storeNumber") or "",
            "store_name": store.get("storeName") or "",
            "city": store.get("city") or "",
            "state": store.get("state") or "",
            "distance": store.get("storeDistanceWithUnit") or "",
            "status": availability.get("pickupDisplay", "unknown"),
            "quote": availability.get("pickupSearchQuote", "No pickup message"),
        })
    return results


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
            "User-Agent": "AppleStockMonitor-GitHubActions/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"Discord returned HTTP {response.status}")


def build_payload(zip_code, selected, rows, errors):
    available_rows = [r for r in rows if r[2].get("status") == "available"]

    if available_rows:
        content = "@everyone 🚨 **APPLE STOCK AVAILABLE**"
        title = "🚨 IN STOCK — Apple Pickup Available"
        description = (
            f"Found **{len(available_rows)} available pickup option(s)** "
            f"near ZIP **{zip_code}**."
        )
        color = 0xE74C3C
    else:
        content = "🔎 Apple stock check completed."
        title = "Apple Stock Check — No Availability"
        description = f"No selected model is currently available near ZIP **{zip_code}**."
        color = 0x7F8C8D

    fields = []
    for product_name in selected:
        product_rows = [r for r in rows if r[0] == product_name]
        available = [r for r in product_rows if r[2].get("status") == "available"]

        if available:
            lines = []
            for _, _, store in available[:5]:
                lines.append(
                    f"✅ **{store.get('store_name', 'Unknown')}** — "
                    f"{store.get('quote', 'Available')} "
                    f"({store.get('distance', '')})"
                )
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "GitHub Actions Apple Stock Monitor"},
        }],
    }


def main():
    zip_code = env("ZIP_CODE", "03079")
    webhook = env("DISCORD_WEBHOOK")
    selected = parse_selected_products()

    if not zip_code.isdigit() or len(zip_code) != 5:
        raise ValueError("ZIP_CODE must be a 5-digit ZIP code.")

    rows = []
    errors = []

    print(f"Checking ZIP {zip_code}")
    print("Products:", ", ".join(selected))

    for product_name in selected:
        part_number = PRODUCTS[product_name]
        print(f"Checking {product_name} ({part_number})...")
        try:
            stores = fetch_product(zip_code, part_number)
        except Exception as exc:
            msg = f"{product_name}: {type(exc).__name__}: {exc}"
            print("ERROR:", msg)
            errors.append(msg)
            continue

        for store in stores:
            rows.append((product_name, part_number, store))

        available = [s for s in stores if s.get("status") == "available"]
        print(f"  Apple returned {len(stores)} stores; {len(available)} available.")

    payload = build_payload(zip_code, selected, rows, errors)
    post_discord(webhook, payload)
    print("Discord summary sent.")

    # Keep Actions green even if some Apple queries fail; Discord gets the errors.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
