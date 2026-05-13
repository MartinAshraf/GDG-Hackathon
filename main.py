# main.py
import json
from researcher import run_researcher_agent
from coder import run_coder_agent

# ── Step 1: Run Researcher ──
print("=" * 50)
print("STEP 1 — RESEARCHER AGENT")
print("=" * 50)

# These are the packages your target repo uses
dependencies = {"packages": ["Flask", "PyJWT", "requests"]}

threat_report = run_researcher_agent(dependencies)

# Save it (researcher already does this, but just to be safe)
with open("threat_report.json", "w") as f:
    json.dump(threat_report, f, indent=2)

print("\n✓ Researcher done — threat_report.json saved")

# ── Step 2: Run Coder ──
print("\n" + "=" * 50)
print("STEP 2 — CODER AGENT")
print("=" * 50)

# The repo you want to scan and fix
TARGET_REPO = "https://github.com/erev0s/VAmPI"

result = run_coder_agent(repo_url=TARGET_REPO, threat_report_path="threat_report.json")

print("\n✓ Coder done — fix_report.json saved")
print("\n🎉 Pipeline complete!")
