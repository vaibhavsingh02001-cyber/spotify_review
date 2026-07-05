# 📊 Problem Statement — Milestone 3: Weekly Review Pulse AI Agent (MCP)

> **Context:** This milestone builds on your previous work to create an **AI Agent** that automates the aggregation and reporting of public app reviews. The agent will ingest store feedback, cluster them into key themes, and deliver findings using Google Docs and Gmail via Model Context Protocol (MCP) integrations.

---

## 1. Goal

The goal is to turn raw mobile-store feedback into a weekly pulse your team can scan in minutes: **what users care about, what they actually said, and what to do next.**

Reviews are already public; your job is to aggregate, theme, summarize, and deliver that insight through familiar surfaces—**Google Docs** for the written pulse and **Gmail** for a draft you can send yourself—without handling credentials or REST wiring yourself.

### End-to-End Flow (What "Done" Looks Like)

1. **Pull** recent App Store and Play Store reviews for your product (within the rules below).
2. **Cluster** them into a small set of themes and distill a one-page weekly note.
3. **Put** that note where stakeholders can read it (Google Docs).
4. **Create** a draft email to yourself (or an alias) that contains or links to that pulse (Gmail).

---

## 2. Deliverables

The weekly one-page pulse must include:
*   **Top themes** (what people are talking about most).
*   **Real user quotes** (verbatim snippets from reviews, no invented wording).
*   **Three action ideas** (concrete next steps grounded in the themes).
*   **Email Draft:** A draft email containing this weekly note (or a clear pointer to it) sent to yourself.

---

## 3. Audience & Impact ("Who This Helps")

| Audience | Why / Benefit |
| :--- | :--- |
| **Product / Growth** | Prioritize fixes and improvements from real signals |
| **Support** | Align messaging with what users are actually saying |
| **Leadership** | One-page health check without drowning in raw reviews |

---

## 4. What You Must Build

1. **Review Ingestion & Processing:**
   *   Import reviews from roughly the last **8–12 weeks** (using fields such as rating, title, text, date—whatever your export provides).
   *   Group reviews into at most **5 themes** (examples: onboarding, KYC, payments, statements, withdrawals—pick what fits your product).
2. **Weekly Note Generation:**
   *   Generate a weekly one-page note containing:
       *   Top **3 themes** (subset of your themes as appropriate)
       *   **3 user quotes**
       *   **3 action ideas**
3. **Gmail Integration:**
   *   Draft an email with the note to yourself or an alias.

---

## 5. Integrations: Google Docs & Gmail via MCP

> [!IMPORTANT]
> **MCP-First Integration Constraint**
> Use MCP (Model Context Protocol) servers for Google Docs and Gmail—for example, creating or updating the pulse document and creating the draft message—rather than integrating Google APIs directly (no bespoke OAuth client + REST client code as the primary integration path).
> 
> MCP servers expose tools your agent or app can call; lean on that pattern so Docs and Gmail stay consistent with the course tooling and avoid duplicating auth and HTTP plumbing.
> 
> *(Choose MCP servers or connectors your environment provides for Docs and Gmail; the requirement is MCP-first, not "call Google APIs manually".)*

---

## 6. Key Constraints

> [!CAUTION]
> Compliance with these constraints is mandatory to ensure project success and alignment with privacy standards.

*   **Reviews:** Use public review exports only—no scraping behind store logins or terms-of-service-violating automation.
*   **Themes:** Maximum **5 themes** for clustering; the written pulse highlights the top **3**.
*   **Length:** Keep the note scannable and **≤ 250 words** where applicable.
*   **Privacy:** Do not include PII—no usernames, emails, device IDs, or other identifiable reviewer data in any artifact. Quotes should be anonymous and stripped of sensitive details as needed.
