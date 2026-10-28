# Project Overview: Clearpath (GroundedPath)

## What is this Project?

**Clearpath (GroundedPath)** is a local-first, research-oriented personal finance system that helps people take control of their money by combining **data-driven tracking, deterministic financial calculations, and a verification-first AI advisor**. 

It is built as a Major Project by integrating the ideas from two IEEE research papers into one fully working application. The goal is not just to build a finance tracker, but to solve the **trust problem** in AI-based financial advice.

## Problem Statement

Most existing personal finance apps and AI chatbots fall short in one or more of these areas:

- **Lack of trust in AI advice** – Many AI financial advisors give vague answers or hallucinate numbers without showing how they were calculated.
- **Generic advice** – Most apps give one-size-fits-all tips instead of advice based on a user's actual income, expenses, budgets, goals, and debts.
- **No accountability for numbers** – AI models can confidently give incorrect interest, EMI, or affordability numbers with no way to verify them.
- **Poor timing of financial education** – Financial literacy is taught separately from real-life money decisions, making it harder to apply.
- **Privacy concerns** – Many apps require linking bank accounts or uploading sensitive financial data to third-party servers.
- **Over-reliance on market predictions** – Some AI finance tools push risky "get rich quick" advice instead of focusing on budgeting, debt payoff, and savings.

## What Problem Does This Project Solve?

Clearpath tackles these issues by following a simple rule: **"Compute first, explain later."**

### Core Solutions

| Problem | Solution in Clearpath |
| --- | --- |
| **Unverified AI numbers** | A **Numeric Claim Verifier** checks every number the advisor gives against actual tool-computed values. If a number isn't supported, it's rejected or replaced with a deterministic answer. |
| **Advice not tied to user data** | The advisor is **tool-grounded**. It only uses your real transactions, budgets, goals, debts, assets, and cash flow to answer questions. |
| **Generic tips** | **Just-in-Time (JIT) Nudges** are generated from your actual spending behavior. For example, if you're overspending in a budget category, you'll get a nudge with the exact numbers, not a generic "save more" message. |
| **Lack of practical financial education** | **Contextual Learning** links short, cited literacy modules to the decisions you're making. You learn exactly what you need, right when you need it. |
| **Privacy & data security** | **Local-first design**. All data stays in a local SQLite database. Sensitive fields like notes/descriptions can be encrypted at rest. No bank account linking is required. |
| **Confusion between advice types** | Clear separation between **calculation** and **explanation**. Calculators, budgets, and debt payoffs are purely deterministic. The LLM is only used to explain, never to do the math. |
| **No way to measure nudges** | Every nudge action (Accepted/Dismissed) is logged. The **Momentum** page shows real acceptance rates, not fake engagement metrics. |
| **Unreliable forecasts** | Expense forecasting uses a transparent, reproducible ML model with hold-out evaluation, shown clearly on the Insights page with confidence levels. |

## Key Idea: Neuro-Symbolic Approach

Clearpath uses a **neuro-symbolic** design:

- **Symbolic (Deterministic)** – All math (EMI, SIP, debt payoff, affordability, budgets, net worth) is done by rule-based engines. These are always correct.
- **Neural (LLM)** – Used only when available to understand natural language questions, plan which tools to use, and explain results in simple English.
- **Verification Layer** – Acts as a bridge. It ensures the neural part never overrides the symbolic part's numbers.

## Real-World Impact

- **For Students & Beginners** – Learn personal finance concepts alongside their actual finances instead of memorizing theory.
- **For Budget-Conscious Users** – Get honest, data-backed answers about "Can I afford this?" before spending.
- **For People in Debt** – Compare Avalanche vs Snowball strategies with exact interest saved and months saved.
- **For Privacy-Conscious Users** – Manage finances completely offline without sharing data with third-party finance apps.
- **For Researchers** – A reproducible testbed to study grounded AI, numeric verification, and just-in-time nudges.

## Objectives

1. **Build a working full-stack personal finance system** with all core modules (transactions, budgets, goals, debts, assets).
2. **Implement a verification-first AI advisor** that eliminates numeric hallucinations.
3. **Apply just-in-time financial education** based on real user context.
4. **Ensure complete transparency** by showing tool traces, verification results, and citations.
5. **Keep it local-first and privacy-oriented** with no forced third-party integrations.
6. **Make it research-worthy** with a reproducible evaluation harness and honest reporting.

## Summary

**In short:** Clearpath solves the problem of *"Can I actually trust AI to give me correct numbers for my personal finances?"* 

By forcing the AI to compute through verified tools, showing its reasoning, and educating users at the right time, Clearpath delivers **honest, personalized, and verifiable financial guidance** — without compromising privacy.