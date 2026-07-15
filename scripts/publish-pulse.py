#!/usr/bin/env python3
"""
publish-pulse.py
----------------
Phase 6 — MCP Server Integration: Publish Weekly Pulse

Reads the latest approved weekly-pulse-YYYY-MM-DD.md from output/,
then uses the Google Docs & Gmail APIs (same tools as the deployed
MCP Server at https://mcpserver-lopftmp3qyw6maunexx63v.streamlit.app/)
to:

  1. search_documents  -> check for an existing pulse doc (avoid duplicates)
  2. create_document   -> create a new Google Doc titled "Weekly Review Pulse - ..."
  3. append_text       -> write the full pulse markdown content into the doc
  4. create_gmail_draft -> create a Gmail draft with the pulse + Doc URL

Credentials are read from .env (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
GOOGLE_ACCESS_TOKEN, GOOGLE_REFRESH_TOKEN).

Usage:
  python scripts/publish-pulse.py
  python scripts/publish-pulse.py --pulse-file output/weekly-pulse-2026-07-15.md
  python scripts/publish-pulse.py --dry-run
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://mcpserver-lopftmp3qyw6maunexx63v.streamlit.app/")


def parse_args():
    parser = argparse.ArgumentParser(description="Phase 6: Publish weekly pulse via MCP tools")
    parser.add_argument("--pulse-file", type=str, default=None, help="Path to pulse markdown file")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without calling APIs")
    parser.add_argument("--recipient", type=str, default=None, help="Gmail draft recipient email")
    return parser.parse_args()


def get_google_credentials():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        print("[!] Run: pip install google-auth google-auth-httplib2 google-api-python-client")
        sys.exit(1)

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    access_token = os.getenv("GOOGLE_ACCESS_TOKEN", "").strip()
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("[!] Missing Google OAuth credentials in .env")
        print("    Required: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
        print("    Tip: Get these from your MCP Server token.json after OAuth flow")
        sys.exit(1)

    SCOPES = [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/gmail.compose",
    ]

    creds = Credentials(
        token=access_token or None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    if creds.expired or not creds.valid:
        try:
            creds.refresh(Request())
            print("[+] OAuth token refreshed.")
            _update_env_token(creds.token)
        except Exception as e:
            print(f"[!] Token refresh failed: {e}")
            sys.exit(1)

    return creds


def _update_env_token(new_token):
    env_file = ROOT / ".env"
    try:
        content = env_file.read_text(encoding="utf-8")
        if "GOOGLE_ACCESS_TOKEN=" in content:
            content = re.sub(r"^GOOGLE_ACCESS_TOKEN=.*$", f"GOOGLE_ACCESS_TOKEN={new_token}", content, flags=re.MULTILINE)
        else:
            content += f"\nGOOGLE_ACCESS_TOKEN={new_token}\n"
        env_file.write_text(content, encoding="utf-8")
        print("[+] Updated GOOGLE_ACCESS_TOKEN in .env")
    except Exception as e:
        print(f"[~] Could not auto-update .env token: {e}")


def get_docs_client(creds):
    from googleapiclient.discovery import build
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def get_drive_client(creds):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_gmail_client(creds):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def search_documents(drive, query):
    try:
        results = drive.files().list(
            q=f"name contains '{query}' and mimeType='application/vnd.google-apps.document' and trashed=false",
            fields="files(id, name, webViewLink)",
            orderBy="modifiedTime desc",
            pageSize=10,
        ).execute()
        files = results.get("files", [])
        return [{"id": f["id"], "name": f["name"], "url": f.get("webViewLink", "")} for f in files]
    except Exception as e:
        print(f"[!] search_documents failed: {e}")
        return []


def create_document(drive, title):
    file_metadata = {"name": title, "mimeType": "application/vnd.google-apps.document"}
    doc = drive.files().create(body=file_metadata, fields="id, webViewLink").execute()
    return {"id": doc["id"], "url": doc.get("webViewLink", "")}


def append_text(docs, document_id, text):
    requests = [{"insertText": {"location": {"index": 1}, "text": text}}]
    docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return True


def create_gmail_draft(gmail, to, subject, body):
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft_body = {"message": {"raw": raw_message}}
    draft = gmail.users().drafts().create(userId="me", body=draft_body).execute()
    return {"draft_id": draft["id"], "message_id": draft.get("message", {}).get("id", "")}


def find_latest_pulse():
    pulse_files = sorted(OUTPUT_DIR.glob("weekly-pulse-*.md"), reverse=True)
    return pulse_files[0] if pulse_files else None


def extract_date_range(pulse_text):
    match = re.search(r"#\s*Weekly Review Pulse[^\n]*?-+\s*(.+)", pulse_text)
    if match:
        return match.group(1).strip()
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def pii_scan(text):
    # Pre-remove date patterns (YYYY-MM-DD) to avoid false positive phone matches (Edge Case 3.3)
    text_no_dates = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "DATE", text)
    text_no_dates = re.sub(r"\b\d{4}-\d{2}\b", "DATE", text_no_dates)
    patterns = {"email": r"[\w.-]+@[\w.-]+\.\w+", "phone": r"[\+]?[\d\s\-\(\)]{7,15}", "handle": r"@\w+"}
    findings = []
    for name, pattern in patterns.items():
        for m in re.findall(pattern, text_no_dates):
            if len(m.strip()) > 4:
                findings.append(f"{name}: {m.strip()}")
    return findings


def main():
    args = parse_args()
    today_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("=" * 60)
    print("  Phase 6 - Publish Weekly Pulse via MCP Tools")
    print(f"  MCP Server: {MCP_SERVER_URL}")
    print("=" * 60)

    # Step 1: Locate pulse file
    if args.pulse_file:
        pulse_path = Path(args.pulse_file)
        if not pulse_path.is_absolute():
            pulse_path = ROOT / pulse_path
    else:
        pulse_path = find_latest_pulse()

    if not pulse_path or not pulse_path.exists():
        print("[!] No weekly pulse file found in output/")
        print("    Run: python scripts/generate-pulse.py")
        sys.exit(1)

    print(f"\n[*] Pulse file: {pulse_path}")
    with open(pulse_path, "r", encoding="utf-8") as f:
        pulse_content = f.read()

    word_count = len(re.findall(r"\b\w+\b", pulse_content))
    print(f"[*] Word count: {word_count}")

    # Step 2: PII gate
    print("\n[*] Running PII scan...")
    pii_findings = [f for f in pii_scan(pulse_content) if "Generated by" not in f]
    if pii_findings:
        print(f"[!] BLOCKED: PII detected. Fix before publishing.")
        for finding in pii_findings[:5]:
            print(f"    - {finding}")
        sys.exit(1)
    print("[+] PII scan passed.")

    date_range = extract_date_range(pulse_content)
    doc_title = f"Weekly Review Pulse - {date_range}"
    print(f"\n[*] Doc title: {doc_title}")

    # Dry-run
    if args.dry_run:
        recipient = args.recipient or os.getenv("OPERATOR_EMAIL", "operator@example.com")
        print("\n" + "-" * 60)
        print("  DRY RUN - No API calls will be made")
        print("-" * 60)
        print(f"  [1] search_documents(query='Weekly Review Pulse')")
        print(f"  [2] create_document(title='{doc_title}')")
        print(f"  [3] append_text(doc_id=<new>, text=<{word_count} words>)")
        print(f"  [4] create_gmail_draft(to='{recipient}', subject='{doc_title}')")
        print("\n[+] Dry run complete. Remove --dry-run to publish.")
        return

    # Step 3: Auth
    print("\n[*] Authenticating with Google APIs...")
    creds = get_google_credentials()
    docs = get_docs_client(creds)
    drive = get_drive_client(creds)
    gmail = get_gmail_client(creds)
    print("[+] Google clients ready.")

    # Step 4: search_documents (dedup)
    print(f"\n[*] MCP Tool: search_documents -> dedup check...")
    existing = search_documents(drive, "Weekly Review Pulse")
    week_matches = [d for d in existing if date_range in d["name"]]

    doc_id = None
    doc_url = None

    if week_matches:
        doc_id = week_matches[0]["id"]
        doc_url = week_matches[0]["url"]
        print(f"[~] Existing doc found: {week_matches[0]['name']}")
        print(f"    URL: {doc_url}")
        print("[~] Using existing doc (skipping create + append).")
    else:
        # Step 5: create_document
        print(f"\n[*] MCP Tool: create_document -> '{doc_title}'")
        result = create_document(drive, doc_title)
        doc_id = result["id"]
        doc_url = result["url"]
        print(f"[+] Doc created: {doc_url}")

        # Step 6: append_text
        print(f"\n[*] MCP Tool: append_text -> {word_count} words...")
        time.sleep(1)
        append_text(docs, doc_id, pulse_content)
        print("[+] Content written to Google Doc.")

    # Step 7: create_gmail_draft
    recipient = args.recipient or os.getenv("OPERATOR_EMAIL", "").strip()
    if not recipient:
        print("[!] No recipient. Set OPERATOR_EMAIL in .env or use --recipient")
        sys.exit(1)

    product_name = os.getenv("PRODUCT_NAME", "Spotify")
    email_body = f"""Hi team,

Here is this week's review pulse for {product_name}.

{pulse_content}

Full Google Doc: {doc_url}

---
Generated by Weekly Pulse Agent
MCP Server: {MCP_SERVER_URL}
"""
    print(f"\n[*] MCP Tool: create_gmail_draft -> to: {recipient}")
    draft_result = create_gmail_draft(gmail, recipient, doc_title, email_body)
    draft_id = draft_result["draft_id"]
    print(f"[+] Gmail draft created! ID: {draft_id}")

    # Step 8: Audit report
    report = {
        "run_date": today_tag,
        "mcp_server_url": MCP_SERVER_URL,
        "pulse_file": str(pulse_path),
        "pulse_word_count": word_count,
        "pii_scan": "passed",
        "doc_title": doc_title,
        "doc_id": doc_id,
        "doc_url": doc_url,
        "draft_id": draft_id,
        "draft_recipient": recipient,
        "draft_subject": doc_title,
        "tools_called": [
            "search_documents",
            "create_document" if not week_matches else "(skipped - existing doc)",
            "append_text" if not week_matches else "(skipped - existing doc)",
            "create_gmail_draft",
        ],
        "status": "success",
    }
    report_path = OUTPUT_DIR / f"publish-report-{today_tag}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Audit report: {report_path}")
    print("\n" + "=" * 60)
    print("  Phase 6 Complete!")
    print(f"  Google Doc: {doc_url}")
    print(f"  Gmail Draft ID: {draft_id}")
    print(f"  Next: Review draft in Gmail and click Send")
    print("=" * 60)


if __name__ == "__main__":
    main()
