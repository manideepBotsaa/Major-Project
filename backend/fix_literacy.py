import json
import re
from pathlib import Path

path = Path(__file__).resolve().parent / "app" / "data" / "literacy.json"
raw = path.read_text(encoding="utf-8")
fixed = []
for line in raw.splitlines():
    match = re.match(r'^(    "content": ")(.*)("(,?))$', line)
    if match:
        body = match.group(2).replace('"', '\\"')
        line = match.group(1) + body + match.group(3)
    fixed.append(line)
modules = json.loads("\n".join(fixed))

quizzes = {
    "budget-as-a-decision": [
        ("What is the main purpose of a budget?",
         ["To restrict every category equally", "To decide in advance what your money should do", "To record every receipt perfectly", "To maximise income"],
         1, "A budget is a decision about priorities and ordering, not a blanket restriction."),
        ("In the 50/30/20 starting point, what does the 20% represent?",
         ["Rent and utilities", "Discretionary entertainment", "Saving and debt repayment", "Taxes"],
         2, "The 20% bucket is for saving and debt repayment; needs and wants take 50% and 30%."),
        ("How should someone with irregular income build a monthly budget?",
         ["Use the best month's income", "Budget from a conservative baseline and direct surpluses deliberately", "Avoid budgeting until income stabilises", "Borrow to fill the gap every month"],
         1, "A conservative baseline prevents a good month from becoming a permanent spending expectation."),
    ],
    "emergency-fund": [
        ("What is an emergency fund for?",
         ["Funding holidays", "Covering unpredictable necessary expenses without borrowing", "Earning the highest possible return", "Paying regular monthly bills"],
         1, "The fund exists to absorb shocks so they do not become high-interest debt."),
        ("A common starting target for an emergency fund is:",
         ["One week of income", "Three to six months of essential expenses", "Ten years of expenses", "One month of discretionary spending"],
         1, "Three months is a common first target; six months suits variable income or dependants."),
        ("Where should emergency money be held?",
         ["In equity funds for growth", "In a liquid, stable, separate account", "In a long-term fixed deposit with penalties", "In the same account as everyday spending"],
         1, "Liquidity, stability, and separation are the key properties."),
    ],
    "cash-flow-vs-income": [
        ("What does cash flow measure that income does not?",
         ["How much money arrived", "How much money actually stayed after outflow", "Your credit score", "Your tax slab"],
         1, "Income is capacity; cash flow is the result after spending and obligations."),
        ("What is the simplest fix for a timing gap between bills and salary?",
         ["Ignore the bill", "Keep a cash buffer to cover the gap", "Take a new credit card", "Reduce your income"],
         1, "A buffer covers the period between when money arrives and when it must leave."),
        ("How is the savings rate calculated?",
         ["Income divided by expenses", "Expenses divided by income", "(Income minus expenses) divided by income", "Total savings divided by age"],
         2, "The savings rate expresses the unspent share of income as a percentage."),
    ],
    "debt-and-interest": [
        ("How can you estimate the monthly interest on a credit-card balance?",
         ["Balance multiplied by APR", "Balance multiplied by APR divided by 12", "Balance divided by APR", "APR divided by the balance"],
         1, "APR is an annual rate; dividing by twelve approximates the monthly cost."),
        ("Which debt payoff method targets the highest APR first?",
         ["Snowball", "Avalanche", "Minimum-only", "Consolidation"],
         1, "Avalanche minimises total interest by attacking the most expensive debt first."),
        ("Why can paying only the minimum be a trap?",
         ["It always damages your credit score", "The minimum may barely cover monthly interest", "It is illegal", "It automatically increases the APR"],
         1, "If the minimum is close to the interest charge, the principal barely falls."),
    ],
    "credit-score": [
        ("What credit-utilisation level is often recommended?",
         ["Below 30% of available credit", "Exactly 100%", "Above 80%", "Utilisation has no effect"],
         0, "Lower utilisation signals less dependence on credit; below 30% is a common guideline."),
        ("Does checking your own credit score lower it?",
         ["Yes, every check lowers it", "No, checking your own score does not lower it", "Only if you check more than once a year", "Only for secured cards"],
         1, "Self-checks are typically soft enquiries and do not affect the score."),
        ("Why can closing an old credit card hurt your score?",
         ["It reduces available credit and shortens history", "It automatically creates a late payment", "It changes your income", "It cancels all your loans"],
         0, "Closing a card can raise utilisation and shorten the average account age."),
    ],
    "goal-based-saving": [
        ("What makes a savings goal actionable?",
         ["A vague intention to save more", "A named amount, date, and reason", "A high return assumption", "A new credit card"],
         1, "Specificity lets you calculate a contribution and evaluate trade-offs."),
        ("Where should money for a goal less than three years away generally be held?",
         ["Stable, liquid instruments", "Concentrated equity", "Crypto", "Long-dated illiquid assets"],
         0, "Short horizons need certainty of value, not maximum expected return."),
        ("If you are behind on a goal, what is the honest set of options?",
         ["Ignore it and hope", "Contribute more, extend the date, or lower the target", "Borrow to fund it", "Increase the assumed return"],
         1, "Choosing one lever deliberately is better than quietly abandoning the goal."),
    ],
    "compounding": [
        ("What does the Rule of 72 estimate?",
         ["The tax rate on gains", "The years for money to double at a given return", "The inflation rate", "The optimal savings rate"],
         1, "Divide 72 by the annual return percentage to approximate the doubling time."),
        ("Why do fees matter so much over long periods?",
         ["They are charged only once", "They compound against you every year", "They are tax-deductible", "They increase returns"],
         1, "A recurring fee reduces the base on which future returns are earned."),
        ("What is the main risk for a long-horizon investor?",
         ["Temporary volatility itself", "Selling during a decline", "Missing a single day of gains", "Owning a diversified fund"],
         1, "Volatility is tolerable if the horizon is long; panic-selling converts it into a permanent loss."),
    ],
    "inflation": [
        ("If savings earn 4% and inflation is 5%, what happens to purchasing power?",
         ["It rises by 9%", "It falls by about 1%", "It stays the same", "It rises by 1%"],
         1, "The real return is approximately nominal minus inflation, here about -1%."),
        ("Why is holding years of expenses in cash risky?",
         ["Cash can be stolen", "It slowly loses purchasing power to inflation", "It earns too much interest", "It is illiquid"],
         1, "Cash is useful for certainty, but it is not a long-term growth asset."),
        ("When setting a long-term goal, what should you be clear about?",
         ["Whether the amount is in today's rupees or future rupees", "The colour of the spreadsheet", "The bank's logo", "The number of accounts"],
         0, "Mixing real and nominal amounts is a common source of false confidence."),
    ],
    "insurance": [
        ("What is the core purpose of insurance?",
         ["To earn high returns", "To transfer a low-probability, high-cost risk", "To avoid all financial loss", "To replace a budget"],
         1, "Insurance is most useful when a loss would be financially devastating and is unpredictable."),
        ("Why is term life often clearer than an investment-linked policy?",
         ["It has no insurance component", "It separates inexpensive protection from investing", "It guarantees higher returns", "It cannot be cancelled"],
         1, "Term cover is relatively inexpensive; investing the difference separately is more transparent."),
        ("Which risk is usually a poor fit for insurance?",
         ["A hospitalisation that could cost months of income", "Death of a breadwinner", "A small, predictable phone repair", "A major health diagnosis"],
         2, "Small predictable expenses are better handled by a budget or sinking fund."),
    ],
    "investing-basics": [
        ("What does diversification primarily reduce?",
         ["All risk", "Concentration risk", "Taxes", "Inflation"],
         1, "Diversification spreads exposure but cannot eliminate market risk."),
        ("Why are broad index funds popular with long-term investors?",
         ["They guarantee profits", "They offer diversified exposure at low cost", "They never fall", "They avoid taxes"],
         1, "Low costs and broad exposure make them a simple default for many investors."),
        ("Risk tolerance has two parts: ability and what else?",
         ["Willingness", "Age", "Salary", "Credit score"],
         0, "Ability is financial; willingness is emotional. A suitable portfolio respects both."),
    ],
    "tax-basics-india": [
        ("How do income-tax slabs work?",
         ["Every rupee is taxed at your highest rate", "Only the income above each threshold is taxed at the higher rate", "All income is taxed at a flat rate", "Slabs apply only to investments"],
         1, "Slab rates apply to portions of income, so a raise cannot reduce your take-home pay."),
        ("What is tax deducted at source (TDS)?",
         ["A final tax that cannot be adjusted", "A prepayment of tax that is reconciled when you file", "A penalty", "An investment"],
         1, "TDS is withheld during the year and reconciled against your final liability."),
        ("Why should you verify tax rules before acting?",
         ["Rules change and this module is conceptual", "Taxes are optional", "Only accountants pay tax", "The rules are secret"],
         0, "Tax law changes; always check the current provisions or consult a professional."),
    ],
    "behavioural-finance": [
        ("What is present bias?",
         ["Preferring immediate rewards over larger future ones", "Believing the present is worse than the past", "Avoiding all decisions", "Overestimating inflation"],
         0, "Present bias makes saving feel costly now even when the future benefit is larger."),
        ("Which design is a good response to present bias?",
         ["Decide to try harder next month", "Automate saving on payday", "Keep cash in a spending account", "Check prices daily"],
         1, "Pre-commitment moves the decision to a moment when the future self has more influence."),
        ("What makes a nudge ethically acceptable?",
         ["It is hidden from the user", "It removes all choices", "It is transparent and helps the user's own stated goal", "It maximises the company's revenue"],
         2, "Transparency and alignment with the user's goals distinguish a nudge from manipulation."),
    ],
}

for module in modules:
    questions = quizzes[module["slug"]]
    module["quiz"] = [
        {"prompt": prompt, "options": options, "correct_index": correct, "explanation": explanation}
        for prompt, options, correct, explanation in questions
    ]

path.write_text(json.dumps(modules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(modules)} modules with {sum(len(m['quiz']) for m in modules)} questions.")
