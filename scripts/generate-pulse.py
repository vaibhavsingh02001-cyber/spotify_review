#!/usr/bin/env python3
"""Theme Analysis and Weekly Pulse Generation using Groq LLM.

Performs:
  - Local statistics aggregation
  - Stratified sampling (~120 reviews, over-representing negative feedback)
  - LLM Call 1: Theme Clustering (forces JSON format, saving to themes.json)
  - Theme ranking & top 3 selection
  - LLM Call 2: Pulse Composition (markdown format)
  - Post-generation validation (word count, verbatim quotes check, sections count)
  - Persistence of pulse to output/weekly-pulse-YYYY-MM-DD.md

Usage:
  python scripts/generate-pulse.py --ref-date YYYY-MM-DD
"""

import argparse
import json
import os
import re
import string
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Set up paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load env
load_dotenv(ROOT / ".env")

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Basic English stop words
STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", 
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", 
    "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", 
    "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", 
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", 
    "with", "about", "against", "between", "into", "through", "during", "before", "after", 
    "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", 
    "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", 
    "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", 
    "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", 
    "should", "now", "app", "groww", "spotify"
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate weekly review pulse")
    parser.add_argument(
        "--ref-date",
        type=str,
        default=None,
        help="Reference date for file naming and analysis YYYY-MM-DD (default: today)",
    )
    return parser.parse_args()


def extract_keywords(reviews_list: list[dict], top_n: int = 20) -> list[tuple[str, int]]:
    word_counts = {}
    for r in reviews_list:
        full_text = (r.get("title", "") + " " + r.get("text", "")).lower()
        full_text = full_text.translate(str.maketrans("", "", string.punctuation))
        words = re.findall(r"\b\w+\b", full_text)
        for w in words:
            if w not in STOP_WORDS and len(w) > 2:
                word_counts[w] = word_counts.get(w, 0) + 1
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_words[:top_n]


def select_llm_sample(reviews_list: list[dict], target_cap: int = 120) -> list[dict]:
    strata = {1: [], 2: [], 3: [], 4: [], 5: []}
    for r in reviews_list:
        rating = int(r["rating"])
        if rating in strata:
            strata[rating].append(r)
            
    for rating in strata:
        strata[rating].sort(key=lambda x: (x["date"], len(x["text"])), reverse=True)
        
    targets = {
        1: int(target_cap * 0.35),
        2: int(target_cap * 0.25),
        3: int(target_cap * 0.15),
        4: int(target_cap * 0.15),
        5: int(target_cap * 0.10)
    }
    
    selected = []
    strata_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    overflow = 0
    for rating in [1, 2, 3, 4, 5]:
        available = len(strata[rating])
        target = targets[rating]
        take = min(available, target)
        selected.extend(strata[rating][:take])
        strata_counts[rating] = take
        overflow += (target - take)
        
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
                    
    selected.sort(key=lambda x: x["date"], reverse=True)
    return selected


def clean_text_for_match(t: str) -> str:
    return re.sub(r"\W+", "", t).lower()


def verify_quotes_verbatim(quotes_found: list[str], sample_reviews: list[dict]) -> bool:
    for q in quotes_found:
        q_clean = clean_text_for_match(q)
        if not q_clean:
            continue
        found = False
        for r in sample_reviews:
            r_text_clean = clean_text_for_match(r.get("text", ""))
            r_title_clean = clean_text_for_match(r.get("title", ""))
            if q_clean in r_text_clean or q_clean in r_title_clean:
                found = True
                break
        if not found:
            print(f"[!] Quote validation failed: Quote {repr(q)} is not verbatim from any sample review.")
            return False
    return True


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[!] GROQ_API_KEY environment variable is missing. Cannot perform LLM calls.")
        print("[!] Please check the README and setup credentials first.")
        sys.exit(1)
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        print("[!] 'groq' package is not installed. Run 'pip install -r requirements.txt'.")
        sys.exit(1)


def make_groq_call(client, messages, response_format=None, max_retries=3) -> str:
    backoff = 2
    for i in range(max_retries):
        try:
            params = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.1,
            }
            if response_format:
                params["response_format"] = response_format
                
            response = client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            print(f"[!] Groq API call failed: {e}. Retrying in {backoff}s...")
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError("Failed to call Groq API after multiple retries.")


def main():
    args = parse_args()
    
    # Setup reference date tag
    if args.ref_date:
        ref_tag = args.ref_date
    else:
        ref_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
    norm_file = PROCESSED_DIR / "normalized-reviews.json"
    if not norm_file.exists():
        print(f"[!] Normalized reviews file not found at: {norm_file}")
        sys.exit(1)
        
    with open(norm_file, "r", encoding="utf-8") as f:
        reviews = json.load(f)
        
    if not reviews:
        print("[!] No normalized reviews available to process.")
        sys.exit(1)
        
    print(f"[*] Loaded {len(reviews)} normalized reviews.")
    
    # 1. Compute Local Statistics
    total_reviews = len(reviews)
    star_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in reviews:
        star_distribution[r["rating"]] += 1
        
    avg_rating = sum(r["rating"] for r in reviews) / total_reviews
    negative_count = star_distribution[1] + star_distribution[2]
    negative_review_pct = negative_count / total_reviews
    
    dates = [r["date"] for r in reviews if r.get("date")]
    date_range = f"{min(dates)} to {max(dates)}" if dates else "unknown range"
    
    keywords = extract_keywords(reviews, top_n=20)
    keywords_str = ", ".join([f"{k} ({v})" for k, v in keywords])
    
    stats = {
        "total_reviews": total_reviews,
        "star_distribution": star_distribution,
        "avg_rating": round(avg_rating, 2),
        "date_range": date_range,
        "negative_review_pct": round(negative_review_pct * 100, 2),
        "top_keywords": keywords
    }
    
    print("[*] Local Statistics aggregated:")
    print(f"    Total: {total_reviews} reviews | Avg Rating: {stats['avg_rating']}")
    print(f"    Date Range: {date_range}")
    print(f"    Negative Ratio: {stats['negative_review_pct']}%")
    print(f"    Top Keywords: {keywords_str}")
    
    # 2. Select Stratified Sample for LLM (120 reviews)
    sample_reviews = select_llm_sample(reviews, target_cap=120)
    print(f"[+] Prepared stratified sample of {len(sample_reviews)} reviews for LLM.")
    
    # Initialize Groq client
    client = get_groq_client()
    
    # 3. LLM Call 1 - Theme Clustering
    print("[*] Sending theme clustering call to Groq...")
    
    sample_reviews_formatted = [
        {
            "rating": r["rating"],
            "title": r["title"],
            "text": r["text"],
            "date": r["date"]
        }
        for r in sample_reviews
    ]
    
    system_prompt_1 = (
        "You are an expert product analyst specializing in mobile app store feedback.\n"
        "Your task is to analyze user reviews and cluster them into distinct, non-overlapping themes.\n"
        "Always respond in valid JSON format matching the requested schema."
    )
    
    user_prompt_1 = (
        "Identify up to 5 recurring themes in the following app reviews.\n"
        "For each theme, provide:\n"
        "- theme_name: short label (e.g., \"App Crashes\", \"Slow KYC\")\n"
        "- description: 2-3 sentence summary\n"
        "- review_count: approximate number of reviews in this theme\n"
        "- sentiment: \"positive\" | \"negative\" | \"mixed\"\n"
        "- sample_quotes: 2-3 verbatim, anonymized quotes from the reviews\n\n"
        f"Statistics:\n{json.dumps(stats, indent=2)}\n\n"
        f"Reviews:\n{json.dumps(sample_reviews_formatted, indent=2)}\n\n"
        "Respond in valid JSON only with the following structure:\n"
        "{\n"
        "  \"themes\": [\n"
        "    {\n"
        "      \"theme_name\": \"...\",\n"
        "      \"description\": \"...\",\n"
        "      \"review_count\": 10,\n"
        "      \"sentiment\": \"...\",\n"
        "      \"sample_quotes\": [\"...\", \"...\"]\n"
        "    }\n"
        "  ]\n"
        "}"
    )
    
    messages_1 = [
        {"role": "system", "content": system_prompt_1},
        {"role": "user", "content": user_prompt_1}
    ]
    
    clustering_json = make_groq_call(client, messages_1, response_format={"type": "json_object"})
    
    # Save themes.json
    themes_file = PROCESSED_DIR / "themes.json"
    try:
        themes_data = json.loads(clustering_json)
        with open(themes_file, "w", encoding="utf-8") as f:
            json.dump(themes_data, f, indent=2, ensure_ascii=False)
        print(f"[+] Saved theme clustering output to: {themes_file}")
    except Exception as e:
        print(f"[!] Error parsing/saving themes.json: {e}")
        print("Clustering raw output:")
        print(clustering_json)
        sys.exit(1)
        
    # Rank themes by count descending and pick top 3
    themes = themes_data.get("themes", [])
    themes.sort(key=lambda x: x.get("review_count", 0), reverse=True)
    top_3_themes = themes[:3]
    print(f"[*] Top 3 Themes selected: {', '.join([t['theme_name'] for t in top_3_themes])}")
    
    # 4. LLM Call 2 - Pulse Composition & Validation Loop
    system_prompt_2 = (
        "You are writing a weekly review pulse for a product team.\n"
        "You must follow the requested markdown structure exactly and adhere to all word count and verification constraints."
    )
    
    user_prompt_2 = (
        "Using the top 3 themes and quotes below, write a scannable one-page note.\n\n"
        "Structure (MUST follow exactly):\n"
        "1. Top 3 Themes — 2–3 sentence summary each (under a ## 🔥 Top Themes This Week header)\n"
        "2. What Users Are Saying — 3 anonymized verbatim quotes with star ratings (under a ## 💬 What Users Are Saying header)\n"
        "3. Recommended Actions — 3 concrete next steps, tied to themes (under a ## 🎯 Recommended Actions header)\n\n"
        "Constraints:\n"
        "- Maximum 250 words total\n"
        "- No PII — no names, emails, device IDs\n"
        "- Quotes must be verbatim from the provided data (do not invent or modify)\n\n"
        f"Themes:\n{json.dumps(top_3_themes, indent=2)}\n\n"
        "Write the pulse in markdown format."
    )
    
    messages_2 = [
        {"role": "system", "content": system_prompt_2},
        {"role": "user", "content": user_prompt_2}
    ]
    
    pulse_markdown = ""
    validated = False
    validation_attempts = 3
    
    print("[*] Sending pulse composition call to Groq...")
    
    for attempt in range(1, validation_attempts + 1):
        print(f"[*] Validation Attempt {attempt}/{validation_attempts}...")
        
        pulse_markdown = make_groq_call(client, messages_2)
        
        # Word count check
        word_count = len(re.findall(r"\b\w+\b", pulse_markdown))
        print(f"    - Word Count: {word_count} (Limit: 250)")
        
        # Sections check
        has_themes_hdr = bool(re.search(r"##.*Top Themes", pulse_markdown, re.IGNORECASE))
        has_quotes_hdr = bool(re.search(r"##.*What Users Are Saying", pulse_markdown, re.IGNORECASE))
        has_actions_hdr = bool(re.search(r"##.*Recommended Actions", pulse_markdown, re.IGNORECASE))
        print(f"    - Section Headers: Top Themes: {has_themes_hdr}, Quotes: {has_quotes_hdr}, Actions: {has_actions_hdr}")
        
        # Quotes check
        quotes_found = re.findall(r'>\s*"(.*?)"', pulse_markdown)
        if not quotes_found:
            quotes_found = re.findall(r'>\s*\'(.*?)\'', pulse_markdown)
        print(f"    - Found {len(quotes_found)} blockquote quotes in pulse.")
        
        # Verbatim quotes validation
        verbatim_ok = verify_quotes_verbatim(quotes_found, sample_reviews)
        
        # Actions check
        # Check if there are 3 list items in action plan
        action_section = ""
        action_match = re.search(r"##.*Recommended Actions.*?\n(.*)", pulse_markdown, re.DOTALL | re.IGNORECASE)
        if action_match:
            action_section = action_match.group(1)
        actions_found = re.findall(r"^\s*\d+\.\s+.*", action_section, re.MULTILINE)
        if not actions_found:
            actions_found = re.findall(r"^\s*-\s+.*", action_section, re.MULTILINE)
        print(f"    - Found {len(actions_found)} action items in pulse.")
        
        # Check overall criteria
        if word_count <= 250 and has_themes_hdr and has_quotes_hdr and has_actions_hdr and len(quotes_found) == 3 and verbatim_ok and len(actions_found) == 3:
            print("[+] Pulse successfully passed all post-generation validation checks!")
            validated = True
            break
        else:
            print("[!] Validation failed. Constructing feedback loop for retry...")
            # Build feedback prompt
            feedback = "Your previous output failed the validation checks. Please rewrite the pulse keeping the following errors in mind:\n"
            if word_count > 250:
                feedback += f"- The text was {word_count} words. It MUST be strictly less than 250 words.\n"
            if not (has_themes_hdr and has_quotes_hdr and has_actions_hdr):
                feedback += "- Missing required ## headers for 'Top Themes This Week', 'What Users Are Saying', and 'Recommended Actions'.\n"
            if len(quotes_found) != 3:
                feedback += f"- Found {len(quotes_found)} quotes, but there must be EXACTLY 3 blockquote quotes formatted as `> \"quote\"`.\n"
            if not verbatim_ok:
                feedback += "- One or more quotes were not verbatim from the reviews. You MUST copy quotes EXACTLY word-for-word from the themes data.\n"
            if len(actions_found) != 3:
                feedback += f"- Found {len(actions_found)} action items. There must be EXACTLY 3 numbered actions.\n"
                
            messages_2.append({"role": "assistant", "content": pulse_markdown})
            messages_2.append({"role": "user", "content": feedback})
            
    if not validated:
        print("[!] Validation loop completed without success. Saving the last generated pulse anyway.")
        
    # Format and save output
    pulse_file = OUTPUT_DIR / f"weekly-pulse-{ref_tag}.md"
    
    # Append the review volume footer dynamically
    footer = f"\n---\n*Generated by Weekly Pulse Agent · {total_reviews} reviews · {ref_tag}*"
    if footer not in pulse_markdown:
        pulse_markdown += footer
        
    with open(pulse_file, "w", encoding="utf-8") as f:
        f.write(pulse_markdown)
        
    print(f"\n[+] Weekly Pulse successfully saved to: {pulse_file}")
    print("---")
    print(pulse_markdown)
    print("---")


if __name__ == "__main__":
    main()
