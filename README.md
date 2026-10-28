# Clearpath (GroundedPath)

Clearpath is a local-first, research-oriented personal finance platform that combines a **deterministic financial engine** with a **verification-first AI advisor** and **just-in-time (JIT) financial literacy**. It is built as a major project that integrates ideas from two IEEE papers into one working system, with a focus on *numeric correctness, explainability, and reproducibility*.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Demo Credentials](#demo-credentials)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Testing](#testing)
- [Research & Evaluation](#research--evaluation)
- [Documentation](#documentation)
- [Security & Privacy](#security--privacy)
- [Disclaimer](#disclaimer)
- [License](#license)

## Overview

Clearpath has two identities working together:

- **Product (Clearpath)** – A clean, privacy-focused personal finance app for tracking transactions, budgets, goals, debts, assets and net worth.
- **Research System (GroundedPath)** – A neuro-symbolic advisor that *computes first, explains later*. Every numeric answer comes from deterministic tools, and all model-generated numeric claims are verified against those computed values before being displayed.

The core principle: **Language may explain. Only deterministic tools may compute.**

## Key Features

### Personal Finance Management
- **Dashboard** – At-a-glance net worth, cash flow, financial health score, safe-to-spend, and recent activity.
- **Transactions** – Manual entry, CSV import/export, category suggestions, encrypted notes/descriptions.
- **Budgets** – Monthly budgets with pace tracking, daily remaining, rollover support, and smart suggestions.
- **Goals** – Goal tracking with Monte Carlo projections, required monthly contributions, and contribution history.
- **Debts** – Avalanche vs Snowball payoff comparison, extra payment simulation, interest/months saved, and utilisation tracking.
- **Assets & Net Worth** – Balance sheet view with liquid vs illiquid separation and asset mix visualisation.
- **Insights** – Forecasting, recurring detection, anomalies, category trends, and "What-If" scenarios.

### Verification-First AI Advisor
- **Tool-grounded reasoning** – The advisor plans with an LLM only if configured, but all numbers are fetched from deterministic tools.
- **Numeric claim verifier** – Rejects unsupported figures, re-plans or falls back to fully deterministic answers.
- **Tool trace & citations** – Every answer shows which tools were used, verification results, and links to relevant literacy modules.
- **Session history** – Persistent, private conversations with feedback (helpful/not helpful).
- **Fully offline capable** – Runs entirely without an LLM key using the rules-based deterministic provider.

### Just-in-Time Financial Literacy
- **Contextual learning** – Short, cited modules that appear at the moment of a decision.
- **Quizzes & progress** – Track completion, streaks, and points.
- **Knowledge search** – Semantic search over curated literacy content, used by both the Learn page and the advisor.

### Gamification & Nudges
- **Momentum** – Points, streaks, badges, and activity history.
- **JIT Nudges** – Five use cases inspired by Paper 2 (budget pace/overrun, low savings/emergency runway, high-interest debt, goal-at-risk, subscription/anomaly/payday timing). Every nudge shows the numbers that triggered it and is logged as accepted/dismissed.

### Research Harness
- **Synthetic personas** – Reproducible personas for benchmarking.
- **Benchmarks** – Categorization, expense forecasting, advisor grounding/routing, and nudge simulation.
- **Machine-readable results** – Outputs to `research/results/summary.json` with figures and reproducibility metadata.

## Architecture

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐
│  React + Vite│────▶│  Flask API   │────▶│  Deterministic Engines  │
│  (Frontend)  │     │  (Routes/    │     │  (Analytics, Goals,     │
│              │     │   Services)  │     │   Debts, Forecasting,   │
└─────────────┘     └─────────────┘     │   Advisor, Nudges)     │
                                        └─────────────┘
                                                 │
                                                 ▼
                                            ┌─────────┐
                                            │  SQLite  │
                                            │  (Local) │
                                            └─────────┘
```

- **Frontend**: Routed SPA with protected layout, contexts for auth/toast, shared UI components, charts, and rich pages.
- **Backend**: Flask app factory (`app/`), blueprinted routes, SQLAlchemy models, service layer for all financial logic, security utilities, and advisor orchestration with verification.
- **Data**: Local SQLite database in `backend/instance/finance.db`. Sensitive fields (descriptions/notes) are encrypted at rest when `FIELD_ENCRYPTION_KEY` is configured.
- **Advisor**: Pluggable provider (auto-selects Gemini if `GEMINI_API_KEY` set, else OpenAI-compatible if `LLM_BASE_URL` set, else deterministic). Verifier runs regardless of provider.

## Tech Stack

| Layer | Technologies |
| --- | --- |
| **Frontend** | React 18, Vite 5, React Router DOM, Tailwind-inspired custom CSS, Lucide React, Recharts, React Markdown |
| **Backend** | Flask 3, Flask-CORS, SQLAlchemy 2, Werkzeug, PyJWT, Cryptography, python-dotenv, scikit-learn, pandas, numpy, pytest |
| **Database** | SQLite (local-first) |
| **Research** | Python scripts under `research/` with reproducible seeds |

## Project Structure

```text
project/
├── backend/                # Flask API
│   ├── app/                # App factory, models, routes, services, security
│   ├── instance/           # SQLite DB (finance.db)
│   ├── tests/              # Pytest suite
│   ├── requirements.txt
│   └── run.py
├── frontend/               # React + Vite SPA
│   ├── src/                # Components, pages, context, lib, styles
│   ├── package.json
│   └── vite.config.js
├── research/               # Evaluation harness & results
├── paper/                  # IEEE LaTeX paper
├── docs/                   # PROJECT_REPORT, DEMO_SCRIPT, EVALUATION_PROTOCOL, etc.
└── README.md
```

## Getting Started

### Prerequisites
- [Python 3.11+](https://www.python.org/) (tested with 3.13)
- [Node.js 18+](https://nodejs.org/) and npm
- Git (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd project
   ```

2. **Setup Backend**
   ```bash
   cd backend
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. **Setup Frontend**
   ```bash
   cd frontend
   npm install
   ```

## Demo Credentials

Use these to explore the app immediately with pre-seeded data:

| Field | Value |
| --- | --- |
| **Email** | `demo@clearpath.app` |
| **Password** | `DemoPass123!` |

You can log in manually with these, or click **"Open the demo workspace"** on the login page for one-click access. The demo includes ~18 months of history, 684 transactions, goals, debts, assets, and literacy progress.

## Environment Variables

Key variables from `backend/.env.example`:

| Variable | Default | Notes |
| --- | --- | --- |
| `SECRET_KEY` | `replace-with-a-long-random-secret` | Flask secret key (change in production) |
| `DATABASE_URL` | `sqlite:///finance.db` | DB connection string |
| `FRONTEND_ORIGIN` | `http://localhost:5173,http://127.0.0.1:5173` | CORS allowed origins |
| `FIELD_ENCRYPTION_KEY` | *(empty)* | Required for encrypting notes/descriptions at rest. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. App still works if unset (with a warning). |
| `ALLOW_DEMO_LOGIN` | `true` | Enables demo login |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | `demo@clearpath.app` / `DemoPass123!` | Demo account credentials |
| `LLM_PROVIDER` | `auto` | `auto`, `deterministic`, `gemini`, or `openai_compatible` |
| `GEMINI_API_KEY` | *(empty)* | For Google Gemini |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | *(empty)* | For OpenAI-compatible providers (e.g., Ollama) |
| `LLM_REQUIRE_NUMERIC_VERIFICATION` | `true` | Enforces numeric claim verification |

## Running the Project

### Option 1: Development (Hot Reload)

**Terminal 1 - Backend**
```bash
cd backend
.\.venv\Scripts\activate  # Windows
python run.py
```
Backend runs at `http://127.0.0.1:5000`

**Terminal 2 - Frontend**
```bash
cd frontend
npm run dev
```
Frontend runs at `http://localhost:5173`

### Option 2: Production Build

**Build frontend**
```bash
cd frontend
npm run build
```
The built assets go to `frontend/dist/`. You can serve them with any static server or integrate with Flask.

**Run backend**
```bash
cd backend
.\.venv\Scripts\activate
python run.py
```

### Database Setup (if starting fresh)

The repo already includes a seeded `backend/instance/finance.db`. If you need to reset/seed:

```bash
cd backend
.\.venv\Scripts\activate
python -m flask --app run.py reset-db
python -m flask --app run.py seed-demo
python -m flask --app run.py seed-literacy
```

## Testing

Run backend tests from the backend directory with the venv activated:

```bash
cd backend
.\.venv\Scripts\activate
python -m pytest -q
```

Current suite: **31 backend tests passing** (covering planning, affordability, etc.).

## Research & Evaluation

The project includes a full reproducible evaluation harness.

### Generate Results
From the project root:

```bash
python research/generate_personas.py
python research/bench_categorization.py
python research/bench_forecasting.py
python research/bench_advisor.py
python research/simulate_nudges.py
python research/make_figures.py
# Or run everything
python research/run_all.py
```

Results are written to `research/results/summary.json`. The **Research** page in the app will automatically display them once generated. Figures go to `research/results/figures/`.

See `docs/EVALUATION_PROTOCOL.md` for details on metrics, synthetic data policy, and the planned human study.

## Documentation

All supporting documents are in `docs/`:

| Document | Purpose |
| --- | --- |
| `PROJECT_REPORT.md` | Comprehensive project report covering design, implementation, and analysis |
| `DEMO_SCRIPT.md` | Step-by-step demo walkthrough with talking points |
| `EVALUATION_PROTOCOL.md` | Pre-registered evaluation plan, metrics, and limitations |
| `MODEL_CARD.md` | Model/provider details, grounding guarantees, and constraints |
| `THREAT_MODEL.md` | Privacy/security considerations and mitigations |
| `REFERENCES.md` | References to the two IEEE papers and supporting literature |

The paper source is in `paper/main.tex` with `paper/references.bib`.

## Security & Privacy

- **Local-first**: Data stays in your local SQLite database. No bank connections.
- **Authentication**: Passwords hashed with Werkzeug. Sessions use HTTP-only cookies with CSRF protection.
- **Encryption at rest**: Transaction descriptions and notes encrypted with Fernet when `FIELD_ENCRYPTION_KEY` is set.
- **Rate limiting**: Login and chat endpoints are rate-limited.
- **PII minimization**: Advisor redacts/sends minimal context; raw transactions are not sent unless explicitly configured.
- **No fabricated user study**: Research clearly labels synthetic data and states limitations.

## Disclaimer

**Clearpath is an educational planning tool, not a SEBI-registered investment adviser, lender, insurer, or tax advisor.** It does not connect to bank accounts, does not execute transactions, and does not provide personalized investment recommendations. All projections, probabilities, and calculations are for informational and educational purposes only.

## License

This project is developed as an academic major project. See repository details for specific licensing terms if applicable.
