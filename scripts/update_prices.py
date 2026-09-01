"""
Fetches current prices for every ticker in tickers.txt from the Twelve Data
API and writes them to prices.json in the repo root.

Requires an environment variable TWELVE_DATA_API_KEY (set as a GitHub
Actions secret — see the workflow file).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib import request, parse, error

API_KEY = os.environ.get("TWELVE_DATA_API_KEY")
TICKERS_FILE = "tickers.txt"
OUTPUT_FILE = "prices.json"
SECONDS_BETWEEN_REQUESTS = 8  # free tier allows ~8 requests/minute


def load_tickers():
    if not os.path.exists(TICKERS_FILE):
        print(f"No {TICKERS_FILE} found — nothing to fetch.")
        return []
    with open(TICKERS_FILE) as f:
        tickers = [line.strip().upper() for line in f if line.strip() and not line.strip().startswith("#")]
    return tickers


def fetch_one(ticker, attempt=1):
    url = "https://api.twelvedata.com/price?" + parse.urlencode({
        "symbol": ticker,
        "apikey": API_KEY,
    })
    try:
        with request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        if e.code == 429 and attempt < 3:
            print(f"Rate limited fetching {ticker}, waiting 20s and retrying...")
            time.sleep(20)
            return fetch_one(ticker, attempt + 1)
        print(f"WARNING: HTTP error fetching {ticker}: {e}")
        return None
    except error.URLError as e:
        print(f"WARNING: request failed for {ticker}: {e}")
        return None


def fetch_prices(tickers):
    if not tickers:
        return {}
    if not API_KEY:
        print("ERROR: TWELVE_DATA_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    results = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, ticker in enumerate(tickers):
        entry = fetch_one(ticker)
        if isinstance(entry, dict) and "price" in entry:
            try:
                results[ticker] = {
                    "price": float(entry["price"]),
                    "asOf": now_iso,
                }
            except (TypeError, ValueError):
                print(f"WARNING: couldn't parse price for {ticker}: {entry}")
        else:
            print(f"WARNING: no price returned for {ticker}: {entry}")

        if i < len(tickers) - 1:
            time.sleep(SECONDS_BETWEEN_REQUESTS)

    return results


def main():
    tickers = load_tickers()
    fresh = fetch_prices(tickers)

    existing = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            existing = {}

    # Keep the last known good price for any ticker that failed this run.
    existing.update(fresh)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(existing, f, indent=2, sort_keys=True)

    print(f"Wrote {len(fresh)} fresh price(s) to {OUTPUT_FILE}.")


if __name__ == "__main__":
    main()
