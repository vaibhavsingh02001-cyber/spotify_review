#!/usr/bin/env python3
"""Normalize App Store and Play Store reviews into a unified schema.

Performs:
  - Schema mapping
  - PII sanitization
  - Date window filtering (default: 10 weeks)
  - Content quality filtering (emoji strip, min words, English-only)
  - Stratified sampling to cap the LLM corpus at 1000 reviews
  - Generation of normalization summary report

Usage:
  python scripts/normalize-reviews.py --weeks 10
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dateutil import parser
from dotenv import load_dotenv

# Set up paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load env
load_dotenv(ROOT / ".env")

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize and filter reviews")
    parser.add_argument(
        "--weeks",
        type=int,
        default=10,
        help="Review window in weeks (default: 10)",
    )
    parser.add_argument(
        "--ref-date",
        type=str,
        default=None,
        help="Reference date for filtering YYYY-MM-DD (default: today)",
    )
    return parser.parse_args()


def strip_emojis(text: str) -> str:
    """Strip emojis and high-unicode symbols from text."""
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010ffff"  # High unicode planes
        "\u2600-\u27BF"          # Misc symbols & dingbats
        "\u200d"                 # Zero-width joiner
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub("", text)


def has_emoji(text: str) -> bool:
    """Check if text contains emojis or high-unicode symbols."""
    if not text:
        return False
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010ffff"  # High unicode planes
        "\u2600-\u27BF"          # Misc symbols & dingbats
        "\u200d"                 # Zero-width joiner
        "]+", flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))



def sanitize_pii(text: str) -> str:
    """Redact emails, handles, phone numbers, and account IDs."""
    if not text:
        return ""
    
    # 1. Emails
    text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[REDACTED]", text)
    
    # 2. @Handles
    text = re.sub(r"@\w+", "[REDACTED]", text)
    
    # 3. Phone numbers (7-15 digits with spaces/hyphens/parens, optional + prefix)
    phone_pattern = r"(?:\+?\d{1,3}[\s-]?)?\(?\d{3,4}\)?[\s-]?\d{3,4}[\s-]?\d{4}"
    text = re.sub(phone_pattern, "[REDACTED]", text)
    
    # 4. Account/Device IDs (e.g. "user id: 12345")
    id_pattern = r"(?i)(?:user|account|device|customer|client)[\s]*(?:id)?[\s:]*\d+"
    text = re.sub(id_pattern, "[REDACTED]", text)
    
    return text


def is_english(text: str) -> bool:
    """Heuristic to keep English only and remove Hindi/Hinglish."""
    # Check Devanagari script
    if re.search(r"[\u0900-\u097F]", text):
        return False
        
    # Check Romanized Hindi (Hinglish) keywords
    words = set(re.findall(r"\b\w+\b", text.lower()))
    hinglish_specific = {
        "achha", "accha", "bakwas", "bekar", "faltu", "ghatiya", "dhokha", 
        "nahi", "hai", "kya", "kyu", "kyon", "chal", "rha", "raha", "luta", 
        "lut", "paise", "pesa", "chutiya", "bakwaas", "sahi", "mast", "yaar", 
        "didi", "bhai", "sirf"
    }
    
    if len(words.intersection(hinglish_specific)) >= 2:
        return False
        
    return True


def normalize_date(date_str: str) -> str:
    """Parse and normalize date string to YYYY-MM-DD."""
    try:
        dt = parser.parse(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # Regex fallback
        m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        if m:
            return m.group(1)
        return ""


def select_llm_corpus(reviews_list: list[dict], target_cap: int = 1000) -> tuple[list[dict], dict]:
    """Perform stratified sampling by rating, preferring recent and longer text."""
    # Group reviews by rating
    strata = {1: [], 2: [], 3: [], 4: [], 5: []}
    for r in reviews_list:
        rating = int(r["rating"])
        if rating in strata:
            strata[rating].append(r)
            
    # Sort each stratum: recent date first, then longer text length
    for rating in strata:
        strata[rating].sort(key=lambda x: (x["date"], len(x["text"])), reverse=True)
        
    # Target distribution: over-represent negative reviews (1-2★)
    targets = {
        1: int(target_cap * 0.35),
        2: int(target_cap * 0.25),
        3: int(target_cap * 0.15),
        4: int(target_cap * 0.15),
        5: int(target_cap * 0.10)
    }
    
    selected = []
    strata_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    # First pass: try to meet target distribution
    overflow = 0
    for rating in [1, 2, 3, 4, 5]:
        available = len(strata[rating])
        target = targets[rating]
        take = min(available, target)
        selected.extend(strata[rating][:take])
        strata_counts[rating] = take
        overflow += (target - take)
        
    # Second pass: distribute overflow capacity from 1-star upwards
    if overflow > 0:
        for rating in [1, 2, 3, 4, 5]:
            taken = strata_counts[rating]
            available = len(strata[rating]) - taken
            if available > 0:
                take = min(available, overflow)
                selected.extend(strata[rating][taken:taken+take])
                strata_counts[rating] += take
                overflow -= take
                if overflow <= 0:
                    break
                    
    # Sort selected reviews by date descending
    selected.sort(key=lambda x: x["date"], reverse=True)
    return selected, strata_counts


def process_reviews(playstore_file: Path, appstore_file: Path, cutoff_date: datetime) -> tuple[list[dict], dict]:
    stats = {
        "raw_playstore": 0,
        "raw_appstore": 0,
        "after_date_filter": 0,
        "after_pii_sanitization": 0,
        "after_content_filters": 0,
        "per_platform": {"appstore": 0, "playstore": 0},
        "star_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    }
    
    normalized = []
    
    # 1. Parse Play Store CSV
    if playstore_file and playstore_file.exists():
        print(f"[*] Reading Play Store raw file: {playstore_file.name}")
        with open(playstore_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats["raw_playstore"] += 1
                
                # Canonical mapping
                raw_date = row.get("Date", "")
                norm_date = normalize_date(raw_date)
                if not norm_date:
                    continue
                    
                # Date filter
                dt = datetime.strptime(norm_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt < cutoff_date:
                    continue
                stats["after_date_filter"] += 1
                
                # Rating mapping
                try:
                    rating = int(float(row.get("Star Rating", 0)))
                except ValueError:
                    continue
                if not (1 <= rating <= 5):
                    continue
                    
                title = row.get("Review Title", "").strip()
                text = row.get("Review Text", "").strip()
                
                # Drop if empty
                if not text:
                    continue
                
                # PII Sanitization
                text_clean = sanitize_pii(text)
                title_clean = sanitize_pii(title)
                stats["after_pii_sanitization"] += 1
                
                # Content Filters
                if has_emoji(text_clean) or has_emoji(title_clean):
                    continue
                
                text_no_emoji = text_clean
                title_no_emoji = title_clean
                
                # Skip if empty/too short after clean (less than 8 words)
                combined_len = len(re.findall(r"\b\w+\b", title_no_emoji + " " + text_no_emoji))
                if combined_len < 8:
                    continue
                    
                # Language filter
                if not is_english(text_no_emoji):
                    continue
                    
                stats["after_content_filters"] += 1
                stats["per_platform"]["playstore"] += 1
                stats["star_distribution"][rating] += 1
                
                normalized.append({
                    "platform": "playstore",
                    "date": norm_date,
                    "rating": rating,
                    "title": title_no_emoji,
                    "text": text_no_emoji,
                    "source": playstore_file.name
                })
                
    # 2. Parse App Store CSV
    if appstore_file and appstore_file.exists():
        print(f"[*] Reading App Store raw file: {appstore_file.name}")
        with open(appstore_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats["raw_appstore"] += 1
                
                # Canonical mapping
                raw_date = row.get("Updated Date", "")
                norm_date = normalize_date(raw_date)
                if not norm_date:
                    continue
                    
                # Date filter
                dt = datetime.strptime(norm_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if dt < cutoff_date:
                    continue
                stats["after_date_filter"] += 1
                
                # Rating mapping
                try:
                    rating = int(float(row.get("Star Rating", 0)))
                except ValueError:
                    continue
                if not (1 <= rating <= 5):
                    continue
                    
                title = row.get("Title", "").strip()
                text = row.get("Review", "").strip()
                
                # Drop if empty
                if not text:
                    continue
                
                # PII Sanitization
                text_clean = sanitize_pii(text)
                title_clean = sanitize_pii(title)
                stats["after_pii_sanitization"] += 1
                
                # Content Filters
                if has_emoji(text_clean) or has_emoji(title_clean):
                    continue
                
                text_no_emoji = text_clean
                title_no_emoji = title_clean
                
                # Skip if empty/too short after clean (less than 8 words)
                combined_len = len(re.findall(r"\b\w+\b", title_no_emoji + " " + text_no_emoji))
                if combined_len < 8:
                    continue
                    
                # Language filter
                if not is_english(text_no_emoji):
                    continue
                    
                stats["after_content_filters"] += 1
                stats["per_platform"]["appstore"] += 1
                stats["star_distribution"][rating] += 1
                
                normalized.append({
                    "platform": "appstore",
                    "date": norm_date,
                    "rating": rating,
                    "title": title_no_emoji,
                    "text": text_no_emoji,
                    "source": appstore_file.name
                })
                
    return normalized, stats


def main():
    args = parse_args()
    
    # Calculate cutoff date
    ref_date_str = args.ref_date
    if ref_date_str:
        ref_dt = datetime.strptime(ref_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        ref_dt = datetime.now(timezone.utc)
        
    cutoff_date = ref_dt - timedelta(weeks=args.weeks)
    
    # Find latest raw CSV files
    playstore_files = sorted(RAW_DIR.glob("playstore-reviews-*.csv"))
    appstore_files = sorted(RAW_DIR.glob("appstore-reviews-*.csv"))
    
    latest_play = playstore_files[-1] if playstore_files else None
    latest_app = appstore_files[-1] if appstore_files else None
    
    if not latest_play and not latest_app:
        print("[!] No raw CSV files found. Run fetch-reviews.py first.")
        sys.exit(1)
        
    # Process reviews
    normalized, stats = process_reviews(latest_play, latest_app, cutoff_date)
    
    # Save normalized corpus
    norm_file = PROCESSED_DIR / "normalized-reviews.json"
    with open(norm_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved all normalized reviews ({len(normalized)}) to: {norm_file}")
    
    # Perform stratified sampling for LLM corpus
    llm_corpus, strata_counts = select_llm_corpus(normalized, target_cap=1000)
    
    # Save LLM corpus
    llm_file = PROCESSED_DIR / "reviews-for-llm.json"
    with open(llm_file, "w", encoding="utf-8") as f:
        json.dump(llm_corpus, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved LLM capped corpus ({len(llm_corpus)}) to: {llm_file}")
    
    # Generate Normalization Summary report
    total_raw = stats["raw_playstore"] + stats["raw_appstore"]
    summary = {
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "window_weeks": args.weeks,
        "total_raw_reviews": total_raw,
        "after_date_filter": stats["after_date_filter"],
        "after_pii_sanitization": stats["after_pii_sanitization"],
        "after_content_filters": stats["after_content_filters"],
        "llm_corpus_cap": 1000,
        "llm_corpus_count": len(llm_corpus),
        "per_platform": stats["per_platform"],
        "star_distribution": stats["star_distribution"],
        "llm_strata_distribution": strata_counts
    }
    
    summary_file = PROCESSED_DIR / "normalization-summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved normalization summary to: {summary_file}")
    
    print("\n[*] Normalization complete.")
    print(f"Total processed reviews: {len(normalized)}")
    print(f"Total reviews selected for LLM: {len(llm_corpus)}")


if __name__ == "__main__":
    main()
