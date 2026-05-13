# agents/researcher.py
import os
import time

# Libraries for Scrapping
from bs4 import BeautifulSoup
import requests
import json

# For Gemini Api
from google import genai

# os.environ["GEMINI_API_KEY"] = "AIzaSyBe8J0grh-nufu08WVNX-p7amjtHyVAlDY"
myclient = genai.Client(api_key="AIzaSyBe8J0grh-nufu08WVNX-p7amjtHyVAlDY")


# ─────────────────────────────────────────
# PART 1 — SCRAPE GITHUB ADVISORIES
def scrape_github_advisories(package_name):
    url = f"https://github.com/advisories?query={package_name}&type=reviewed"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }
    print(f"\n→ Scraping advisories for: {package_name}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"  ✗ GitHub returned status {response.status_code}")
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        advisory_cards = soup.find_all("div", class_="Box-row")
        if not advisory_cards:
            print(f"  ○ No advisories found")
            return []
        findings = []
        for card in advisory_cards[:5]:
            # ── Title ──
            title_tag = card.find("a", class_="Link--primary")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            # ── Severity ──
            severity_tag = card.find("span", class_="Label")
            severity = (
                severity_tag.get_text(strip=True).upper() if severity_tag else "UNKNOWN"
            )
            # ── Description ──
            desc_tag = card.find("p")
            description = (
                desc_tag.get_text(strip=True) if desc_tag else "No description"
            )
            # ── URL ──
            link = title_tag["href"] if title_tag and title_tag.has_attr("href") else ""
            advisory_url = f"https://github.com{link}" if link else ""
            # Only keep relevant severity levels
            if severity in ["CRITICAL", "HIGH", "MODERATE"]:
                findings.append(
                    {
                        "package": package_name,
                        "title": title,
                        "severity": severity,
                        "description": description,
                        "url": advisory_url,
                    }
                )
        print(f"  ✓ Found {len(findings)} advisories")
        return findings
    except requests.exceptions.Timeout:
        print(f"  ✗ Request timed out")
        return []
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return []


# ─────────────────────────────────────────
# PART 2 — SEND TO GEMINI FOR CLEANUP
# ─────────────────────────────────────────
def build_threat_report(raw_findings, packages):
    """
    Sends raw scraped data to Gemini.
    Returns clean structured threat report.
    """
    if not raw_findings:
        print("  ○ No findings to process")
        return []
    prompt = f"""
    You are a cybersecurity analyst.
    Below is raw data scraped from GitHub Security Advisories
    for a project using these packages:
    {packages}
    Raw advisory data:
    {json.dumps(raw_findings, indent=2)}
    Instructions:
    1. Remove duplicates
    2. Keep only CRITICAL, HIGH, and MODERATE severity issues
    3. For each issue add a "pattern_to_find" field —
    the exact code string a developer would ctrl+F
    to locate this vulnerability in source code
    Examples:
    - PyJWT issue      → "jwt.decode("
    - MD5 issue        → "hashlib.md5("
    - eval issue       → "eval("
    - pickle issue     → "pickle.loads("
    - SQL injection    → "f\\"SELECT"
    - debug mode       → "debug=True"
    Return ONLY a raw JSON array.
    No markdown. No code blocks. No extra text. Just the JSON.
    [
    {{
        "package": "package name",
        "severity": "CRITICAL or HIGH or MODERATE",
        "description": "one sentence — what is the problem",
        "fix": "one sentence — exactly what to do",
        "pattern_to_find": "exact string to search for in code"
    }}
    ]
    """
    try:
        print("\n🤖 Sending to Gemini...")
        response = myclient.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        raw_text = response.text.strip()
        print(f"  Gemini responded ({len(raw_text)} chars)")
        # Try parsing directly first
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Gemini sometimes wraps in ```json ``` — strip it
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            start = raw_text.find("[")
            end = raw_text.rfind("]") + 1
            return json.loads(raw_text[start:end])
    except Exception as e:
        print(f"  ✗ Gemini failed: {e}")
        return []


# ─────────────────────────────────────────
# PART 3 — MAIN FUNCTION
# ─────────────────────────────────────────
def run_researcher_agent(dependencies):
    """
    Main entry point.
    Receives deps dict from github_tool.py
    Returns threat report list for coder.py
    """
    packages = dependencies["packages"]
    print("\n🔍 Researcher Agent starting...")
    print(f"   Packages to scan: {len(packages)}")
    all_raw_findings = []
    # Scrape advisories for each package
    for package in packages:
        findings = scrape_github_advisories(package)
        all_raw_findings.extend(findings)
        time.sleep(1.5)  # be polite to GitHub
    print(f"\n📊 Raw findings collected: {len(all_raw_findings)}")
    if not all_raw_findings:
        print("✓ No vulnerabilities found — project looks clean")
        return []
    # Send to Gemini for cleanup
    threat_report = build_threat_report(all_raw_findings, packages)
    # Print summary
    print(f"\n✓ Threat report ready — {len(threat_report)} issues\n")
    print("─" * 50)
    for item in threat_report:
        print(f"  [{item['severity']}] {item['package']}")
        print(f"   Problem : {item['description'][:60]}...")
        print(f"   Search  : {item['pattern_to_find']}")
        print()
    return threat_report


# ─────────────────────────────────────────
# TEST IT
# ─────────────────────────────────────────

if __name__ == "__main__":
    fake_deps = {"type": "python", "packages": ["Flask", "PyJWT", "requests"]}
    report = run_researcher_agent(fake_deps)
    with open("threat_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("✓ Saved → threat_report.json")
