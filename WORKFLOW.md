# Workflow

This document explains the end-to-end workflow for **Clearpath (GroundedPath)** — from setup to running the app, testing, and generating research results.

## 1. Overview

Clearpath is a local-first personal finance system with two layers:

- **Clearpath (Product)** – Track transactions, budgets, goals, debts, assets, get insights, nudges, and use calculators.
- **GroundedPath (Research)** – A verification-first AI advisor that computes everything with deterministic tools and verifies numeric claims before showing them.

## 2. Project Setup

### Prerequisites
- Python 3.11+ (tested with 3.13)
- Node.js 18+ and npm
- Git

### Initial Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/manideepBotsaa/Major-Project.git
   cd Major-Project
   ```

2. **Backend setup**
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

3. **Frontend setup**
   ```bash
   cd frontend
   npm install
   ```

## 3. Environment Configuration

Edit `backend/.env` as needed. Key settings:

| Variable | Value | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///finance.db` | Local SQLite database |
| `SECRET_KEY` | (random string) | Flask session secret |
| `FIELD_ENCRYPTION_KEY` | (Fernet key) | Encrypts notes/descriptions at rest. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ALLOW_DEMO_LOGIN` | `true` | Enables demo account login |
| `DEMO_EMAIL` | `demo@clearpath.app` | Demo account email |
| `DEMO_PASSWORD` | `DemoPass123!` | Demo account password |
| `LLM_PROVIDER` | `auto` | `auto` \| `deterministic` \| `gemini` \| `openai_compatible` |
| `GEMINI_API_KEY` | (optional) | Google Gemini key |
| `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` | (optional) | For Ollama/OpenAI-compatible models |

> If `FIELD_ENCRYPTION_KEY` is left empty, the app still runs but will show a warning. Encrypted fields just won't be encrypted locally.

## 4. Database Workflow

The DB lives at `backend/instance/finance.db`. It's already seeded with demo data in this repo.

### Fresh setup / reset
```bash
cd backend
.\.venv\Scripts\activate

# Reset all tables
flask --app run.py reset-db

# Seed demo user + 18 months of data
flask --app run.py seed-demo

# Seed financial literacy modules
flask --app run.py seed-literacy
```

### Verify
- Demo user: `demo@clearpath.app` / `DemoPass123!`
- ~684 transactions, goals, debts, assets, nudges, and literacy progress should exist

## 5. Running the Application

### Development Mode (Recommended)

**Terminal 1: Backend**
```bash
cd backend
.\.venv\Scripts\activate
python run.py
```
Runs at: `http://127.0.0.1:5000`

**Terminal 2: Frontend**
```bash
cd frontend
npm run dev
```
Runs at: `http://localhost:5173`

Open `http://localhost:5173`, login with demo credentials or click **"Open the demo workspace"**.

### Production Build
```bash
cd frontend
npm run build
```
Serve `frontend/dist/` via your preferred static server. Backend can still run separately.

## 6. User Workflow (How to Use)

| Step | Action | Notes |
| --- | --- | --- |
| **1** | Login/Demo | Use demo credentials or demo button |
| **2** | Dashboard | Review safe-to-spend, net worth, health score, recent transactions |
| **3** | Transactions | Add manually or import CSV (`date`, `kind`, `amount` required) |
| **4** | Budgets | Set monthly budgets, track pace vs elapsed days, use suggestions |
| **5** | Goals | Create goals with target, contributions, see Monte Carlo projections |
| **6** | Debts | Add debts, compare Avalanche vs Snowball, simulate extra payments |
| **7** | Assets/Net Worth | Add assets, track liquid vs illiquid, view balance sheet |
| **6/7** | Insights | Check forecast, recurring, anomalies, run "What-If" scenarios |
| **8** | Advisor | Ask questions. See tool trace, verification badge, citations |
| **9** | Learn | Complete modules and quizzes for just-in-time education |
| **10** | Momentum | Track nudges, points, streaks, badges |
| **11** | Calculators | Use EMI/SIP/SWP/FIRE/Compound calculators |
| **12** | Research | View evaluation results if harness has been run |
| **13** | Settings | Update profile, change password, export/delete data |

## 7. Testing Workflow

Run all backend tests:
```bash
cd backend
.\.venv\Scripts\activate
python -m pytest -q
```

Expected: `31 passed`

Tests cover core planning logic, affordability checks, and related services.

## 8. Research & Evaluation Workflow

Generate reproducible benchmarks from project root:

```bash
# Activate backend venv if needed for some scripts
cd backend
.\.venv\Scripts\activate
cd ..

# Run harness
python research/generate_personas.py
python research/bench_categorization.py
python research/bench_forecasting.py
python research/bench_advisor.py
python research/simulate_nudges.py
python research/make_figures.py

# Or all at once
python research/run_all.py
```

Outputs:
- `research/results/summary.json` – Consumed by the Research page
- `research/results/figures/` – Charts/visuals
- Logs/config with seeds for reproducibility

## 9. Advisor Workflow (Grounded)

1. User asks a question on `/advisor`
2. Advisor status checked (LLM available or deterministic)
3. Planner selects relevant deterministic tools
4. Tools compute numbers from user's actual ledger/budgets/goals/debts
5. Answer drafted using only tool outputs
6. **Numeric claim verifier** checks every number against allowed computed values
7. If verification passes → show answer with tool trace + citations
8. If verification fails → fallback to deterministic answer (no invented numbers)
9. Feedback logged

## 10. Git Workflow

### Making changes
```bash
git add .
git commit -m "feat: <description>"
git push origin main
```

### Syncing
```bash
git pull origin main
```

## 11. Troubleshooting

| Issue | Fix |
| --- | --- |
| `FIELD_ENCRYPTION_KEY` warning | Normal if unset. Generate a key and add to `.env` if you want encryption. |
| CORS errors | Check `FRONTEND_ORIGIN` in `backend/.env` matches your frontend URL |
| Demo login fails | Ensure `ALLOW_DEMO_LOGIN=true` and DB is seeded (`seed-demo`) |
| Port in use | Kill process on 5000/5173 or change ports in `run.py`/`vite.config.js` |
| Node modules missing | Run `npm install` in `frontend/` |
| Python deps missing | Run `pip install -r requirements.txt` in `backend/` with venv active |

## 12. Quick Reference

- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://127.0.0.1:5000`
- **Demo Login**: `demo@clearpath.app` / `DemoPass123!`
- **DB**: `backend/instance/finance.db`
- **Tests**: `backend/` → `pytest -q`
- **Repo**: [https://github.com/manideepBotsaa/Major-Project](https://github.com/manideepBotsaa/Major-Project)
- **Key Docs**: `README.md`, `docs/PROJECT_REPORT.md`, `docs/DEMO_SCRIPT.md`, `docs/EVALUATION_PROTOCOL.md`
