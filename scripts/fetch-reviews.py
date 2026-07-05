#!/usr/bin/env python3
"""Download public App Store and Play Store reviews for the selected product.

Usage:
  python scripts/fetch-reviews.py --weeks 10
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Set up paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load environment variables
load_dotenv(ROOT / ".env")

# Product Config Defaults (Groww as default product)
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "Groww").strip()
APP_STORE_ID = os.getenv("APP_STORE_ID", "1404871703").strip()
PLAY_PACKAGE = os.getenv("PLAY_PACKAGE", "com.nextbillion.groww").strip()
PLAY_COUNTRY = os.getenv("PLAY_COUNTRY", "in").strip()
APP_STORE_COUNTRIES = [c.strip() for c in os.getenv("APP_STORE_COUNTRIES", "in,us").split(",") if c.strip()]

RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Fetch public reviews for {PRODUCT_NAME}")
    parser.add_argument(
        "--weeks",
        type=int,
        default=10,
        help="Review window in weeks (default: 10)",
    )
    parser.add_argument(
        "--max-play-batches",
        type=int,
        default=300,
        help="Max number of Play Store review batches to paginate (200 reviews/batch)",
    )
    return parser.parse_args()


def fetch_play_store_reviews(package: str, country: str, cutoff_date: datetime, max_batches: int) -> list[dict]:
    print(f"[*] Ingesting Play Store reviews for package '{package}' ({country})...")
    print(f"[*] Cutoff Date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        from google_play_scraper import Sort, reviews
    except ImportError:
        print("[!] google-play-scraper is not installed. Skipping Play Store.")
        return []

    all_reviews = []
    
    # Fetch first batch
    result, continuation_token = reviews(
        package,
        lang="en",
        country=country,
        sort=Sort.NEWEST,
        count=200
    )
    
    if not result:
        print("[-] No reviews found.")
        return []
        
    all_reviews.extend(result)
    print(f"[+] Batch 1: Fetched {len(result)} reviews. Cumulative: {len(all_reviews)}")
    
    batch_count = 1
    while continuation_token and batch_count < max_batches:
        # Check date of the last review in the current batch
        last_review_at = result[-1]["at"]
        if last_review_at.tzinfo is None:
            last_review_at = last_review_at.replace(tzinfo=timezone.utc)
            
        if last_review_at < cutoff_date:
            print(f"[*] Reached reviews older than cutoff ({last_review_at.strftime('%Y-%m-%d')}). Pagination stopped.")
            break
            
        result, continuation_token = reviews(
            package,
            continuation_token=continuation_token
        )
        
        if not result:
            break
            
        all_reviews.extend(result)
        batch_count += 1
        print(f"[+] Batch {batch_count}: Fetched {len(result)} reviews. Cumulative: {len(all_reviews)}")
        
    return all_reviews


def fetch_app_store_reviews(app_id: str, countries: list[str]) -> list[dict]:
    print(f"[*] Ingesting App Store reviews for App ID '{app_id}'...")
    all_reviews = []
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    for country in countries:
        print(f"[*] Querying App Store RSS feed for region: {country.upper()}")
        for page in range(1, 11):
            url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortby=mostrecent/page={page}/json"
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (400, 404):
                    break
                print(f"[!] HTTP Error {e.code} for country {country} page {page}: {e.reason}")
                break
            except Exception as e:
                print(f"[!] Error fetching country {country} page {page}: {e}")
                break
                
            feed = data.get("feed", {})
            entries = feed.get("entry", [])
            if not entries:
                break
            if isinstance(entries, dict):
                entries = [entries]
                
            page_reviews = 0
            for entry in entries:
                if "im:rating" not in entry:
                    # Skip App metadata entry
                    continue
                
                updated = entry.get("updated", {}).get("label", "")
                rating = entry.get("im:rating", {}).get("label", "")
                title = entry.get("title", {}).get("label", "")
                text = entry.get("content", {}).get("label", "")
                author = entry.get("author", {}).get("name", {}).get("label", "")
                version = entry.get("im:version", {}).get("label", "")
                
                all_reviews.append({
                    "Updated Date": updated,
                    "Star Rating": rating,
                    "Title": title,
                    "Review": text,
                    "Author": author,
                    "Version": version,
                    "Country": country
                })
                page_reviews += 1
                
            print(f"[+] Page {page}: parsed {page_reviews} reviews.")
            if page_reviews == 0:
                break
                
    return all_reviews


def save_play_store_csv(reviews_list: list[dict], filename: Path):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Star Rating", "Review Title", "Review Text", "UserName"])
        for r in reviews_list:
            date_str = r["at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r["at"], datetime) else str(r["at"])
            writer.writerow([
                date_str,
                r.get("score", ""),
                "", # Play Store reviews don't typically have separate titles
                r.get("content", ""),
                r.get("userName", "")
            ])
    print(f"[+] Saved {len(reviews_list)} Play Store reviews to: {filename}")


def save_app_store_csv(reviews_list: list[dict], filename: Path):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Updated Date", "Star Rating", "Title", "Review", "Author", "Version", "Country"])
        for r in reviews_list:
            writer.writerow([
                r.get("Updated Date", ""),
                r.get("Star Rating", ""),
                r.get("Title", ""),
                r.get("Review", ""),
                r.get("Author", ""),
                r.get("Version", ""),
                r.get("Country", "")
            ])
    print(f"[+] Saved {len(reviews_list)} App Store reviews to: {filename}")


def main():
    args = parse_args()
    weeks = args.weeks
    
    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    export_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # 1. Fetch Play Store Reviews
    play_reviews = fetch_play_store_reviews(PLAY_PACKAGE, PLAY_COUNTRY, cutoff_date, args.max_play_batches)
    play_file = RAW_DIR / f"playstore-reviews-{export_tag}.csv"
    save_play_store_csv(play_reviews, play_file)
    
    # 2. Fetch App Store Reviews
    app_reviews = fetch_app_store_reviews(APP_STORE_ID, APP_STORE_COUNTRIES)
    app_file = RAW_DIR / f"appstore-reviews-{export_tag}.csv"
    save_app_store_csv(app_reviews, app_file)
    
    print("\n[*] Ingestion complete.")
    print(f"Total Play Store reviews downloaded: {len(play_reviews)}")
    print(f"Total App Store reviews downloaded: {len(app_reviews)}")


if __name__ == "__main__":
    main()
