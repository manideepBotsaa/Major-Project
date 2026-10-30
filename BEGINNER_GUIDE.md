# Beginner's Guide to Clearpath (GroundedPath)

This guide is written for someone who has **never seen this project before**. Follow this step by step to understand what it does, how to use it, and how every feature works.

## 1. What is Clearpath?

**Clearpath** is a smart, private personal finance app. The special thing about it is that it doesn't just "show" your money, it **calculates** it truthfully and **explains** it without guessing.

Think of it as a mix of:

- **A finance tracker** (like tracking expenses/budgets)
- **A debt planner** (like figuring out how to pay loans faster)
- **A financial teacher** (learn only what you actually need)
- **An AI advisor** (but one that *must* show numbers from your own data)

The research name for it is **GroundedPath**. The big idea: *"The AI can explain, but it can never make up numbers."*

## 2. First Time Setup (To Run It)

Before using it, you need to run both the backend and frontend.

### Prerequisites
- Python 3.11+ installed
- Node.js 18+ installed
- VS Code or any terminal

### Steps

1. **Open project folder**
   ```bash
   cd C:\Users\manid\Downloads\project
   ```

2. **Start Backend (API)**
   ```bash
   cd backend
   .\.venv\Scripts\activate
   python run.py
   ```
   Wait till you see `Running on http://127.0.0.1:5000`

3. **Start Frontend (Website)**
   Open a **new** terminal in the same project folder
   ```bash
   cd frontend
   npm run dev
   ```
   Wait till you see `Local: http://localhost:5173`

4. **Open in browser**
   Go to [http://localhost:5173](http://localhost:5173)

## 3. Logging In

On the login page, you have two options.

| Option | Details |
| --- | --- |
| **"Open the demo workspace" (Easiest)** | Click this button. It auto-logs you in with ready-made data. Best for beginners. |
| **Manual Login** | Use these details: `demo@clearpath.app` / `DemoPass123!` |

Once logged in, you'll land on the **Overview (Dashboard)**.

## 4. Understanding the App Feature by Feature

Use this route map on the left sidebar to explore everything.

### A. Workspace (Your Day-to-Day Money)

| Page | What it does | What to try as a beginner |
| --- | --- | --- |
| **Overview** | Your home screen. Shows net worth, income/expenses, "Safe to Spend", financial health, recent transactions. | Look at "Safe to Spend". This tells you honestly *how much you can actually spend today without breaking your budget*. |
| **Transactions** | Your digital money diary. Every rupee that comes in or goes out. | Add a new transaction (Food, Travel etc) or import a CSV. Notice how categories appear. |
| **Budgets** | Set a limit for each category (Food, Rent, Shopping). | Pick "Food & Dining", set ₹5000 for this month. Watch "Days left" and "Per day left" update. |

### B. Plan (Your Future)

| Page | What it does | What to try as a beginner |
| --- | --- | --- |
| **Goals** | Save for something (Emergency Fund, Laptop, Trip). | Create a goal like "Emergency Fund" with target ₹50,000 and monthly contribution. See the "Success estimate". |
| **Debt** | Track loans/cards and see how to become debt-free faster. | Add a small debt (e.g. Credit Card) with balance, APR & minimum. Compare **Avalanche** vs **Snowball** to see interest saved. |
| **Net Worth** | Your balance sheet. (What you OWN) - (What you OWE) = Net Worth | Add an "Asset" (Savings account/cash). See how it affects your net worth instantly. |

### C. Understand (Learn & Get Help)

| Page | What it does | What to try as a beginner |
| --- | --- | --- |
| **Insights** | Deeper analysis. Cashflow charts, forecasts, unusual spending, "What-If" simulator. | Go to "What-If". Try "Reduce Food & Dining by 20%" and see how much extra you'd save in 12 months. |
| **Advisor** | Your **verification-first AI**. Ask anything about *your* money. | Ask: *"Can I afford a ₹10,000 order?"* or *"Where did most of my money go this month?"* Look at "Tool trace" & "Numbers verified". |
| **Momentum** | Nudges + rewards. Shows actions that actually matter. | Check "Active Nudges". Click "Got it" or "Open Budgets". Earn points for acting. |
| **Learn** | Bite-sized finance lessons with quizzes. | Pick any module (e.g. "Budgeting Basics"). Read, take quiz. If you pass, it gets marked as completed. |
| **Calculators** | Pure math tools (no guessing). | Try **EMI Calculator** (Loan amount, rate, tenure) or **SIP Calculator** (Monthly investment). Change numbers and see results instantly. |

### D. Project (Research Side)

| Page | What it does | What to try as a beginner |
| --- | --- | --- |
| **Research** | Shows how this project was tested and evaluated. | Read "What is genuinely new". You'll see why this is different from normal finance apps. |
| **Settings** | Manage your account, password, data export, privacy info. | Look at "Privacy & model". See "Deterministic, fully offline" vs "External LLM configured". |

## 5. The "Magic" Explained Simply

There are 3 things that make this project different. Focus on these first.

### A) Tool-Grounded Advisor
When you ask the Advisor something, it **doesn't guess**. 

1. It picks the right "tool" (like `get_budget_status`, `affordability_check`)
2. That tool runs on your real data and gives exact numbers
3. The AI explains those numbers in plain English
4. A **verifier** checks every number matches what the tool said

**Look for:** `Numbers verified` badge at the top of the AI answer.

### B) Numeric Verification
This is the heart of GroundedPath. 

- If the AI tries to say *"You have ₹12,500 left"* but the tool says *"₹11,800"*, the verifier **blocks it**.
- Instead, it shows the correct number from the tool.
- This prevents AI hallucinations completely.

**Beginner tip:** Always glance at the **"Tool trace"** dropdown under an answer to see which tools were used.

### C) Just-in-Time Nudges
Instead of sending random tips, Clearpath watches your numbers.

Examples you'll see on **Momentum** page:

- **Budget pace** – "You're spending faster than expected this month"
- **High-interest debt** – "Paying extra on your highest APR card saves most interest"
- **Goal at risk** – "You're falling behind on your goal. Increase contribution slightly"
- **Emergency runway** – "Your emergency fund is lower than recommended"

Every nudge shows **why** it appeared with actual figures from your data.

## 6. Beginner Walkthrough (Do This in Order)

Do these 5 minutes in this exact order to learn the whole app.

| Step | Where | Task |
| --- | --- | --- |
| **1.** | **Overview** | Spend 1 min reading "Safe to Spend", "Financial Health", and "Net Worth". |
| **2.** | **Transactions** | Look at existing ones. Try adding one expense with a description. |
| **3.** | **Budgets** | Create/edit a budget. Watch the progress bar and "per day left". |
| **4.** | **Advisor** | Ask *"Can I afford a ₹5,000 shopping purchase?"*. Open **Tool trace** and see it used `affordability_check`. |
| **5.** | **Learn + Momentum** | Go to **Learn** -> complete a module. Then check **Momentum** to see your points increase. |

After doing these 5 steps, you'll understand 90% of how this project works.

## 7. Key Terms to Know

| Term | Simple Meaning |
| --- | --- |
| **Deterministic** | Fixed rules. Same input = same exact answer. No guessing. |
| **Grounded** | The answer is based *only* on your actual data, not general internet knowledge. |
| **Tool Trace** | A log showing "Which calculations did the advisor do?" |
| **Numeric Claim Verifier** | A checker that makes sure every number is correct before showing it. |
| **JIT Nudges** | Helpful alerts that pop up at the *right time* (when they actually matter). |
| **Avalanche vs Snowball** | Two ways to pay debt. *Avalanche* saves more money (highest interest first). *Snowball* gives faster wins (smallest balance first). |
| **Safe to Spend** | How much you can safely spend right now without going over budget or hurting savings. |
| **Net Worth** | Total value of what you own minus what you owe. |
| **Monte Carlo (Goals)** | A way to show a range of possible outcomes instead of a single "perfect" guess. |
| **Neuro-Symbolic** | Combines AI (brain) + Rules (calculator) to get the best of both. |

## 8. Tips for Beginners

- **Start with Demo** – Don't create your own account first. Use the demo to explore freely.
- **Focus on Overview first** – Everything else connects back to it.
- **Always check the Advisor's tool trace** – This is the easiest way to see "how" it got its answer.
- **Don't skip Calculators** – They're the simplest way to understand the deterministic logic.
- **Read the Research page last** – Once you know how the app works, it'll make perfect sense.
- **Use "What-If" on Insights** – This is one of the coolest and most practical features.

## 9. Quick Summary

**Clearpath is built to answer one question: *"Is this AI giving me correct financial advice based on MY money?"***

If the answer to that question is "Yes, I can see it was calculated from my data and verified" – then this project has achieved its goal. 

For a beginner, your job is simple: **Run it, explore the demo, ask the Advisor a question, and look at the tool trace. That alone will teach you everything you need to know about this project.**