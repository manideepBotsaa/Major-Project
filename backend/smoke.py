from app import create_app

app = create_app({"CSRF_ENABLED": False, "TESTING": True})
client = app.test_client()

for path in ["/api/health", "/api/meta"]:
    response = client.get(path)
    print(path, response.status_code)

response = client.post("/api/auth/demo", json={})
print("demo login", response.status_code, response.get_json().get("user", {}).get("name"))
csrf = response.get_json().get("csrf_token")

checks = [
    "/api/insights/overview",
    "/api/budgets",
    "/api/goals",
    "/api/debts",
    "/api/assets",
    "/api/insights/forecast",
    "/api/insights/trends?months=6",
    "/api/insights/recurring",
    "/api/insights/anomalies",
    "/api/nudges",
    "/api/gamification",
    "/api/literacy/modules",
    "/api/literacy/progress",
    "/api/advisor/status",
]
for path in checks:
    response = client.get(path)
    print(path, response.status_code, len(response.data))
    if response.status_code >= 400:
        print(response.get_json())

for question in [
    "Where did my money go last month?",
    "Can I afford a 25000 laptop?",
    "How do I become debt-free faster?",
    "Explain emergency funds.",
    "How much can I save in 6 months?",
]:
    response = client.post("/api/advisor/chat", json={"message": question})
    data = response.get_json()
    print("\nQ:", question)
    print("status", response.status_code, "provider", data.get("provider"))
    if response.status_code == 200:
        print("tools", [c["tool"] for c in data["planner"]["calls"]])
        print("verification", data["verification"]["passed"], data["verification"]["checked"])
        print(data["message"]["content"][:500])
    else:
        print(data)
