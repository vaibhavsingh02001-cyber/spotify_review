# 🔧 GCP Setup Checklist — Phase 1 Runbook

> Step-by-step guide for configuring Google Cloud Platform and MCP servers for the Weekly Review Pulse Agent.

---

## Status Tracker

| # | Step | Status | Date | Notes |
| :---: | :--- | :---: | :--- | :--- |
| 1 | GCP project created | ⬜ | | |
| 2 | Drive API enabled | ⬜ | | |
| 3 | Gmail API enabled | ⬜ | | |
| 4 | OAuth consent screen configured | ⬜ | | |
| 5 | OAuth client ID created | ⬜ | | |
| 6 | Credentials stored in `.env` | ⬜ | | |
| 7 | Drive MCP registered in IDE | ⬜ | | |
| 8 | Gmail MCP registered in IDE | ⬜ | | |
| 9 | OAuth flow completed | ⬜ | | |
| 10 | Drive MCP smoke test — read | ⬜ | | |
| 11 | Drive MCP smoke test — write | ⬜ | | |
| 12 | Gmail MCP smoke test — read | ⬜ | | |
| 13 | Gmail MCP smoke test — write | ⬜ | | |
| 14 | Tool inventory documented | ⬜ | | |

---

## Step 1 — Create Google Cloud Project

1. Navigate to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Configure:
   - **Project name:** `milestone3-weekly-pulse`
   - **Organization:** (leave default or select yours)
4. Click **Create**
5. Wait for creation, then select the new project
6. Copy the **Project ID** from the dashboard

**Record:**
```
Project ID: ____________________________
Project Name: milestone3-weekly-pulse
Created on: ____________________________
```

---

## Step 2 — Enable Required APIs

Navigate to **APIs & Services → Library** and enable each:

| API | Search Term | Status |
| :--- | :--- | :---: |
| Google Drive API | "Drive API" | ⬜ |
| Gmail API | "Gmail API" | ⬜ |

> [!NOTE]
> The MCP servers rely on these underlying APIs. They must be enabled even though you interact via MCP, not direct REST calls.

---

## Step 3 — Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Select user type:
   - **Internal** — if using Google Workspace (recommended, no app verification needed)
   - **External** — if using personal Gmail (requires adding test users)
3. Fill in the form:

| Field | Value |
| :--- | :--- |
| App name | `Weekly Pulse Agent` |
| User support email | Your email |
| App logo | (skip) |
| App domain | (skip) |
| Developer contact | Your email |

4. Click **Save and Continue**
5. Add scopes:
   - `https://www.googleapis.com/auth/drive.file`
   - `https://www.googleapis.com/auth/gmail.compose`
   - `https://www.googleapis.com/auth/gmail.modify`
6. Click **Save and Continue**
7. If External: add your Google account as a **test user**
8. Click **Save and Continue** → **Back to Dashboard**

---

## Step 4 — Create OAuth Client

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Configure:

| Field | Value |
| :--- | :--- |
| Application type | **Desktop application** |
| Name | `Weekly Pulse MCP Client` |

4. Click **Create**
5. Copy the credentials:

```
Client ID:     ____________________________
Client Secret: ____________________________
```

6. Add to your `.env` file:
```env
GOOGLE_CLIENT_ID=<paste Client ID>
GOOGLE_CLIENT_SECRET=<paste Client Secret>
GOOGLE_PROJECT_ID=<paste Project ID from Step 1>
```

> [!CAUTION]
> Never commit `.env` to git. Verify it's listed in `.gitignore`.

---

## Step 5 — Register MCP Servers in IDE

### MCP Server Endpoints

| Server | Endpoint URL |
| :--- | :--- |
| **Drive MCP** | `https://drivemcp.googleapis.com/mcp/v1` |
| **Gmail MCP** | `https://gmailmcp.googleapis.com/mcp/v1` |

### For Cursor IDE

1. Open **Cursor → Settings → Tools & MCP**
2. Click **Add MCP Server**
3. Enter the **Drive MCP** endpoint URL
4. Repeat for **Gmail MCP** endpoint URL
5. When prompted, complete the **OAuth authorization flow**:
   - Sign in with your Google account
   - Grant the requested permissions
   - Wait for the redirect to confirm authorization

### For Antigravity IDE

1. Open **Settings → MCP Configuration** (or check the MCP config file)
2. Add both server endpoints
3. Complete the OAuth flow when prompted

**MCP Config Location:** `_________________________________` *(record path here)*

---

## Step 6 — Connectivity Smoke Tests

Run each test and record the result:

### Drive MCP Tests

| Test ID | Action | Command / Prompt | Result | Status |
| :---: | :--- | :--- | :--- | :---: |
| T1.1 | List files (read-only) | Ask agent: "List my recent Google Drive files" | | ⬜ |
| T1.2 | Create test document | Ask agent: "Create a Google Doc titled 'MCP Test — Delete Me'" | | ⬜ |
| T1.3 | Delete test document | Ask agent: "Delete the doc titled 'MCP Test — Delete Me'" | | ⬜ |

### Gmail MCP Tests

| Test ID | Action | Command / Prompt | Result | Status |
| :---: | :--- | :--- | :--- | :---: |
| T1.4 | List drafts (read-only) | Ask agent: "List my Gmail drafts" | | ⬜ |
| T1.5 | Create test draft | Ask agent: "Create a Gmail draft to myself with subject 'MCP Test'" | | ⬜ |
| T1.6 | Delete test draft | Ask agent: "Delete the draft with subject 'MCP Test'" | | ⬜ |

---

## Step 7 — Document Tool Inventory

After connecting, run `tools/list` on each MCP server and record the actual tool names:

### Drive MCP — Discovered Tools

| # | Tool Name | Description | Notes |
| :---: | :--- | :--- | :--- |
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

### Gmail MCP — Discovered Tools

| # | Tool Name | Description | Notes |
| :---: | :--- | :--- | :--- |
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

---

## Troubleshooting

### Common Issues

| Error | Cause | Fix |
| :--- | :--- | :--- |
| `403 Forbidden` | API not enabled or scope missing | Check APIs & Services → Library; verify OAuth scopes |
| `401 Unauthorized` | OAuth token expired or invalid | Re-run OAuth flow in MCP client |
| `redirect_uri_mismatch` | OAuth client redirect URI doesn't match MCP client | Update redirect URI in GCP Credentials to match your MCP client |
| `access_denied` | Account not in test users list | Add account to OAuth consent screen → Test users |
| MCP server timeout | Network or endpoint issue | Verify endpoint URL; check internet connection |
| `insufficient_scope` | Missing Gmail or Drive scope | Add required scopes to OAuth consent screen |

### If Gmail MCP Returns 403 (Workspace Admin Restriction)

1. Contact your Workspace admin
2. Request that the OAuth app be trusted for your organization
3. Or: switch to a personal Gmail account for development/testing

---

## Phase 1 Sign-Off

Once all checks pass, record completion:

```
Phase 1 completed on: ____________________________
Completed by: ____________________________
All smoke tests: ✅ PASS / ❌ FAIL
Notes: ____________________________
```

---

*Runbook for [implementation.md — Phase 1](document/implementation.md)*
