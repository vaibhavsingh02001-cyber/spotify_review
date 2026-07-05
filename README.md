# 📊 Weekly Review Pulse AI Agent (MCP) — Milestone 3

> An AI agent that turns raw mobile-store feedback into a scannable weekly pulse, publishes it to **Google Docs**, and drafts a **Gmail** message — using **MCP (Model Context Protocol)** servers as the sole integration path to Google Workspace.

---

## 📁 Project Structure

```
milestone3 ai agent/
├── data/
│   ├── raw/                          # Untouched App Store & Play Store exports
│   └── processed/                    # Normalized, PII-free, filtered reviews
├── output/                           # Weekly pulse artifacts (markdown)
├── prompts/                          # LLM system & occasion prompts
├── scripts/                          # Python ingestion, normalization, analysis
├── document/
│   ├── problem statement.md          # Project requirements & constraints
│   ├── architecture.md               # System design & component architecture
│   └── implementation.md             # Phase-wise implementation plan
├── .env.example                      # Required env var names (copy to .env)
├── .gitignore                        # Excludes secrets, raw data, bytecode
├── requirements.txt                  # Python dependencies
└── README.md                         # ← You are here
```

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Detail |
| :--- | :--- |
| **Python** | 3.10 or later |
| **Google Account** | With access to Google Drive and Gmail |
| **Google Cloud Project** | With Drive API and Gmail API enabled |
| **MCP Client** | IDE with MCP support (e.g. Cursor, Antigravity IDE) |
| **Groq API Key** | Free tier at [console.groq.com](https://console.groq.com/) |

### 1. Clone & Setup

```bash
# Clone the repository
git clone <repo-url>
cd "milestone3 ai agent"

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
# Copy the template
copy .env.example .env    # Windows
cp .env.example .env      # macOS/Linux

# Edit .env with your actual keys
```

| Variable | Description |
| :--- | :--- |
| `GROQ_API_KEY` | API key from [Groq Console](https://console.groq.com/) |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID from GCP |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 Client Secret from GCP |
| `GOOGLE_PROJECT_ID` | Your Google Cloud project ID |
| `REVIEW_WINDOW_WEEKS` | Number of weeks to analyze (default: `10`) |
| `LLM_CORPUS_CAP` | Max reviews sent to LLM (default: `1000`) |
| `OPERATOR_EMAIL` | Email for Gmail draft recipient |

### 3. Google Cloud & MCP Setup

See the [GCP Setup Checklist](#gcp-setup-checklist) below.

---

## ☁️ GCP Setup Checklist

> Follow these steps to configure Google Cloud for MCP integration.

### Step 1 — Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name: `milestone3-weekly-pulse` (or your preferred name)
4. Click **Create**
5. Note the **Project ID** → add to `.env` as `GOOGLE_PROJECT_ID`

### Step 2 — Enable APIs

In the GCP Console, navigate to **APIs & Services → Library** and enable:

| API | Purpose |
| :--- | :--- |
| **Google Drive API** | Underlying API for Drive MCP |
| **Gmail API** | Underlying API for Gmail MCP |

### Step 3 — Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Select **External** user type (or **Internal** if using Workspace)
3. Fill in:
   - App name: `Weekly Pulse Agent`
   - User support email: your email
   - Developer contact: your email
4. Add scopes:
   - `https://www.googleapis.com/auth/drive.file`
   - `https://www.googleapis.com/auth/gmail.compose`
   - `https://www.googleapis.com/auth/gmail.modify`
5. Add your Google account as a **test user** (required for External type)
6. Click **Save**

### Step 4 — Create OAuth Client

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Application type: **Desktop application** (or as required by your MCP client)
4. Name: `Weekly Pulse MCP Client`
5. Click **Create**
6. Copy **Client ID** → add to `.env` as `GOOGLE_CLIENT_ID`
7. Copy **Client Secret** → add to `.env` as `GOOGLE_CLIENT_SECRET`

### Step 5 — Configure MCP Servers in IDE

#### MCP Server Endpoints

| Server | Endpoint |
| :--- | :--- |
| **Drive MCP** | `https://drivemcp.googleapis.com/mcp/v1` |
| **Gmail MCP** | `https://gmailmcp.googleapis.com/mcp/v1` |

#### Configuration Steps

**For Cursor:**
1. Open **Settings → Tools & MCP**
2. Add a new MCP server with the Drive MCP endpoint
3. Add a new MCP server with the Gmail MCP endpoint
4. Complete the OAuth flow when prompted
5. Verify both servers show as **Connected**

**For Antigravity IDE:**
1. Open **Settings → MCP Configuration**
2. Add both server endpoints
3. Complete OAuth flow
4. Verify connectivity

### Step 6 — Verify Connectivity (Smoke Tests)

After MCP setup, run these smoke tests:

| Test | MCP Server | Action | Expected |
| :---: | :--- | :--- | :--- |
| T1.1 | Drive MCP | List files (read-only) | Returns file list |
| T1.2 | Drive MCP | Create test doc | Doc appears in Drive |
| T1.3 | Drive MCP | Delete test doc | Cleanup successful |
| T1.4 | Gmail MCP | List drafts (read-only) | Returns draft list |
| T1.5 | Gmail MCP | Create test draft | Draft appears in Gmail |
| T1.6 | Gmail MCP | Delete test draft | Cleanup successful |

> **⚠️ Troubleshooting:** If you get 403 errors, ensure:
> - APIs are enabled in GCP
> - Your account is listed as a test user on the OAuth consent screen
> - The OAuth client type matches your MCP client requirements
> - Required scopes are added to the consent screen

---

## 📋 MCP Tool Inventory

> Document the actual tools discovered from each MCP server below. Run `tools/list` on each server after connecting.

### Drive MCP Tools

| Tool Name | Purpose | Verified |
| :--- | :--- | :---: |
| *(fill after running tools/list)* | | ⬜ |

### Gmail MCP Tools

| Tool Name | Purpose | Verified |
| :--- | :--- | :---: |
| *(fill after running tools/list)* | | ⬜ |

---

## 🔄 Weekly Pipeline Overview

```
Raw Exports → Normalize → PII Scrub → Filter → Theme (LLM) → Pulse (LLM) → Google Doc (MCP) → Gmail Draft (MCP)
```

| Phase | What Happens | Key Script |
| :--- | :--- | :--- |
| **Ingestion** | Import + normalize App Store & Play Store CSVs | `scripts/fetch-reviews.py` |
| **Analysis** | Theme clustering + pulse generation via Groq LLM | `scripts/generate-pulse.py` |
| **Publish** | Create Google Doc + Gmail draft via MCP | MCP tool calls from agent |

---

## 🔐 Security & Privacy

- **No PII** in any artifact — emails, handles, phones, and IDs are redacted before LLM or MCP processing
- **No credentials in git** — `.env` is gitignored; only `.env.example` (with empty values) is committed
- **MCP-only Google integration** — no direct REST API calls; OAuth handled by MCP client
- **Human gate** — Gmail drafts are reviewed before manual send; no automated email dispatch

---

## 📄 Documentation

| Document | Purpose |
| :--- | :--- |
| [Problem Statement](document/problem%20statement.md) | Requirements, constraints, and deliverables |
| [Architecture](document/architecture.md) | System design, component pipeline, data flow |
| [Implementation Plan](document/implementation.md) | Phase-wise activities, exit criteria, timeline |

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Scripts, data processing, LLM orchestration |
| **LLM** | Groq (`llama-3.3-70b-versatile`) | Theme analysis & pulse composition |
| **MCP Client** | Cursor / Antigravity IDE | Tool discovery, OAuth, transport |
| **MCP Servers** | Google Drive MCP, Gmail MCP | Google Workspace integration |
| **Data** | JSON, CSV, Markdown | Review storage, pulse output |

---

*Built as Milestone 3 of the AI Agent project series.*
