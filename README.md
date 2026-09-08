# 🧭 MarketIntel

**MarketIntel** is a distributed competitive-intelligence platform that crawls competitor e-commerce and social media presences, extracts and scores structured signals, and surfaces them through an analytics dashboard. It combines a stealth browser-scraping cluster, n8n-orchestrated processing pipelines, a multi-perspective ("LLM Council") AI analysis layer, and a FastAPI + Next.js dashboard.


---

## 📖 Overview

**MarketIntel** crawls competitor e-commerce and social media presences, extracts and scores structured signals, and surfaces them through an analytics dashboard. It combines:

- 🕷️ a distributed **stealth browser-scraping cluster**
- 🔀 **n8n-orchestrated** processing pipelines
- 🧠 a multi-perspective **"LLM Council"** AI analysis layer
- 📊 a **FastAPI + Next.js** intelligence dashboard

> Originally built as a PFE (*Projet de Fin d'Études* — final-year engineering graduation project).

## 🏗️ Architecture

\`\`\`
                        ┌─────────────────────────┐
                        │        n8n (5678)        │
                        │  orchestration & workflows│
                        └─────────┬────────────────┘
                                  │ webhooks / triggers
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                          │
┌───────▼────────┐      ┌─────────▼─────────┐      ┌─────────▼─────────┐
│ 🕷️ Stealth      │      │ 🧬 Vector Embedding │      │  🔁 Proxy Manager   │
│ Scraper         │◄────►│ Service (FastAPI)  │      │ (TCP proxy + Redis │
│ Redis-queued,   │      │ sentence-transform. │      │  rotation, n8n-fed)│
│ Playwright/     │      └─────────┬─────────┘      └─────────┬─────────┘
│ SeleniumBase    │                │                          │
└───────┬────────┘                │ embeddings                │ rotating proxies
        │ scraped data             │                          │
        ▼                          ▼                          ▼
┌───────────────────────────────────────────────────────────────────────┐
│              🐘 PostgreSQL — TimescaleDB + pgvector                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                  │
                        ┌─────────▼─────────┐
                        │ 🚪 Dashboard Backend│
                        │ FastAPI (JWT auth) │
                        └─────────┬─────────┘
                                  │ REST API
                        ┌─────────▼─────────┐
                        │ 🖥️ Dashboard Frontend│
                        │ Next.js 16 / React 19│
                        └───────────────────┘
\`\`\`

The scraper is horizontally scalable — each worker node runs multiple isolated processes (multiprocessing, not threading) driving `sb_cdp.Chrome` / Playwright instances, coordinated through a Redis job queue with a dead-letter queue and Prometheus metrics. Sizing guidance lives in [`scraper/README.md`](scraper/README.md).

## ✨ Key Features

| | Feature | Description |
|---|---|---|
| 🕷️ | **Distributed stealth scraping** | Redis-backed job frontier, retry/DLQ handling, horizontal worker scaling, Prometheus metrics |
| 🧩 | **Automatic page classification** | Unknown pages are classified and routed to the right handler |
| 🔁 | **Rotating proxy management** | Standalone TCP proxy with hourly/daily per-domain limits, synced from n8n |
| 🔀 | **n8n-orchestrated pipelines** | Company search, category targeting, reports, failed-job handling, view refresh |
| 🧠 | **LLM Council analysis** | Five parallel analytical lenses feeding a Chairman synthesis node |
| 🧬 | **Vector embeddings** | Multilingual (FR/EN) sentence-transformer embeddings |
| 🔐 | **Full auth flow** | JWT + refresh tokens, registration, email-OTP forgot-password |
| 📈 | **Market intelligence** | Coverage, balance, assortment, availability scoring |
| 🔎 | **SEO intelligence** | Per-domain SEO ranking and dimension scores |
| 📣 | **Social intelligence** | Per-competitor, per-platform social scores |
| ⚡ | **Performance intelligence** | Page-speed aggregate scoring |
| 🎛️ | **Crawl operations panel** | Trigger and monitor scrape jobs from the dashboard |
| 📋 | **Reports** | Generate and manage saved reports |
| 📊 | **Analytics overview** | Aggregated KPIs on the dashboard homepage |

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Scraper | Python · Playwright · SeleniumBase (CDP) · Redis · Prometheus · Docker |
| Proxy Manager | Python (asyncio) · Redis |
| Vector Embedding | Python · FastAPI · sentence-transformers · Hugging Face |
| Orchestration | n8n |
| Dashboard Backend | FastAPI · asyncpg · Pydantic v2 · python-jose · passlib · slowapi · aiosmtplib |
| Dashboard Frontend | Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · SWR · Recharts |
| Database | PostgreSQL + TimescaleDB + pgvector |
| Tooling | `uv` (Python) · npm (frontend) |

## 📂 Repository Structure

<details>
<summary>Click to expand</summary>

\`\`\`
MarketIntel/
├── scraper/                  Distributed stealth browser scraping system
├── proxy_manager/             TCP proxy service with rotation + rate limits
├── vector_embedding/          FastAPI service generating multilingual embeddings
├── dashboard/
│   ├── backend/                FastAPI app (auth, competitors, council, crawl, market, ...)
│   └── frontend/               Next.js dashboard
├── n8n/, docs/n8n/            n8n workflow exports and setup guides
├── PFE_*.json                 n8n workflow exports
├── docs/                       Specs, diagrams, plans
└── scraper_architecture_review.pptx
\`\`\`

</details>

## ✅ Prerequisites

- 🐍 Python 3.11+
- 🟩 Node.js 18+ and npm
- 📦 `uv`
- 🐳 Docker & Docker Compose
- 🐘 PostgreSQL with TimescaleDB + pgvector
- 🔀 An n8n instance
- 🔑 API keys: OpenRouter, Hugging Face (optional), SMTP

## 🚀 Getting Started

### 1️⃣ Scraper Cluster
\`\`\`bash
cd scraper && uv sync
docker-compose up -d redis prometheus
docker-compose up --scale worker=3
\`\`\`

### 2️⃣ Proxy Manager
\`\`\`bash
cd proxy_manager && uv sync
docker-compose up -d
\`\`\`

### 3️⃣ Vector Embedding Service
\`\`\`bash
cd vector_embedding && uv sync
uv run python main.py
\`\`\`

### 4️⃣ n8n Workflows
Import `PFE_*.json`, `n8n/PFE_council_workflow.json`, and `docs/n8n/pfe2_council_*.json`, then follow [`docs/n8n/pfe2_council_setup.md`](docs/n8n/pfe2_council_setup.md) — use your own credentials.

### 5️⃣ Dashboard Backend
\`\`\`bash
cd dashboard/backend && uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload
\`\`\`

### 6️⃣ Dashboard Frontend
\`\`\`bash
cd dashboard/frontend && npm install && npm run dev
\`\`\`

## 🔧 Environment Variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Generate your own — never reuse an example value |
| `SCRAPER_API_BASE_URL` | Scraper's FastAPI base URL |
| `N8N_WEBHOOK_BASE_URL` / `N8N_API_KEY` | n8n integration |
| `CORS_ORIGINS` | Allowed frontend origin(s) |
| `DASHBOARD_PUBLIC_URL` | Callback URL n8n uses |

## 🧪 Testing
\`\`\`bash
cd dashboard/backend && uv run pytest
\`\`\`

## 📚 Documentation

| Path | Contents |
|---|---|
| `docs/specs/` | Feature/design specs (e.g. LLM Council) |
| `docs/diagrams/` | Architecture, deployment, UML |
| `docs/n8n/` | Workflow setup guides |
| `scraper_architecture_review.pptx` | Scraper architecture deck |

## 🔒 Security Note

Older commits included real-looking credentials in example files. Before going public: rotate any leaked credentials, scrub git history, and confirm `.env.example` files only hold placeholders.

## 🗺️ Roadmap

- [ ] Visualize per-lens LLM Council output in the frontend
- [ ] Add a root-level `LICENSE`
- [ ] Consolidate `scraper/schema2.sql`–`schema9.sql` into one migration history


## 👤 Author

**Ilyass Chakroun** — Software Engineer
