"""
Fetches current prices for every ticker in tickers.txt from the Twelve Data
API and writes them to prices.json in the repo root.

Requires an environment variable TWELVE_DATA_API_KEY (set as a GitHub
Actions secret — see the workflow file).
"""
import json
import os
import sys
from datetime import datetime, timezone
from urllib import request, parse, error

API_KEY = os.environ.get("TWELVE_DATA_API_KEY")
TICKERS_FILE = "tickers.txt"
OUTPUT_FILE = "prices.json"


def load_tickers():
    if not os.path.exists(TICKERS_FILE):
        print(f"No {TICKERS_FILE} found — nothing to fetch.")
        return []
    with open(TICKERS_FILE) as f:
        tickers = [line.strip().upper() for line in f if line.strip() and not line.strip().startswith("#")]
    return tickers


def fetch_prices(tickers):
    if not tickers:
        return {}
    if not API_KEY:
        print("ERROR: TWELVE_DATA_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    symbol_param = ",".join(tickers)
    url = "https://api.twelvedata.com/price?" + parse.urlencode({
        "symbol": symbol_param,
        "apikey": API_KEY,
    })

    try:
        with request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except error.URLError as e:
        print(f"ERROR: request failed: {e}", file=sys.stderr)
        sys.exit(1)

    results = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    # Twelve Data returns a flat {"price": "..."} object when only one
    # symbol was requested, or a dict keyed by symbol when multiple were.
    if len(tickers) == 1:
        data = {tickers[0]: data}

    for ticker in tickers:
        entry = data.get(ticker)
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
