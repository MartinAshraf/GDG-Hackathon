import os
import json
import shutil
import tempfile
from google import genai
from git import Repo

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────

myclient = genai.Client(api_key="AIzaSyBe8J0grh-nufu08WVNX-p7amjtHyVAlDY")

# ─────────────────────────────────────────
# PART 1 — CLONE REPO INTO A SANDBOX
# ─────────────────────────────────────────


def clone_to_sandbox(repo_url):
    """
    Clones the target repo into a temp folder (the sandbox).
    This is an isolated copy — original repo is never touched.
    """

    sandbox_dir = tempfile.mkdtemp(prefix="sandbox_")
    print(f"\n📦 Cloning repo into sandbox...")
    print(f"   Sandbox path: {sandbox_dir}")

    try:
        Repo.clone_from(repo_url, sandbox_dir)
        print(f"   ✓ Clone successful")
        return sandbox_dir

    except Exception as e:
        print(f"   ✗ Clone failed: {e}")
        return None


# ─────────────────────────────────────────
# PART 2 — SCAN FILES FOR VULNERABLE PATTERNS
# ─────────────────────────────────────────


def scan_sandbox_for_vulnerabilities(sandbox_dir, threat_report):
    """
    Walks through every Python file in the sandbox.
    For each file, checks if any vulnerable pattern exists.
    Returns a list of hits — file + line + what was found.
    """

    print(f"\n🔍 Scanning sandbox for vulnerable patterns...")
    hits = []

    # Walk through every file in the cloned repo
    for root, dirs, files in os.walk(sandbox_dir):

        # Skip hidden folders like .git
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in files:

            # Only scan Python files
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(root, filename)

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

            except Exception:
                continue

            # Check each line against every known vulnerability pattern
            for line_num, line in enumerate(lines, start=1):
                for threat in threat_report:
                    pattern = threat.get("pattern_to_find", "")

                    if pattern and pattern in line:
                        hits.append(
                            {
                                "file": filepath,
                                "line_number": line_num,
                                "line_content": line.strip(),
                                "pattern_matched": pattern,
                                "package": threat["package"],
                                "severity": threat["severity"],
                                "description": threat["description"],
                                "fix": threat["fix"],
                            }
                        )
                        print(f"   ⚠ [{threat['severity']}] Found '{pattern}'")
                        print(f"     File: {filename} — Line {line_num}")

    print(f"\n   Total hits found: {len(hits)}")
    return hits


# ─────────────────────────────────────────
# PART 3 — ASK GEMINI TO FIX THE CODE
# ─────────────────────────────────────────


def fix_vulnerability_with_gemini(hit):
    """
    Sends the vulnerable line to Gemini.
    Gets back the fixed version.
    """

    prompt = f"""
    You are a senior Python security engineer.

    A vulnerability was found in this line of code:

    Line {hit['line_number']} in {os.path.basename(hit['file'])}:
    {hit['line_content']}

    Vulnerability details:
    - Package   : {hit['package']}
    - Severity  : {hit['severity']}
    - Problem   : {hit['description']}
    - How to fix: {hit['fix']}

    Instructions:
    1. Rewrite ONLY that line (or minimum lines needed) to fix the issue
    2. Keep the same logic — just make it secure
    3. Add a short comment above the fix explaining what you changed
    4. Return ONLY the fixed code lines — no explanation, no markdown, no code blocks

    Fixed code:
    """

    try:
        response = myclient.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text.strip()

    except Exception as e:
        print(f"   ✗ Gemini fix failed: {e}")
        return None


# ─────────────────────────────────────────
# PART 4 — APPLY THE FIX TO THE SANDBOX FILE
# ─────────────────────────────────────────


def apply_fix_to_file(hit, fixed_code):
    """
    Opens the file in the sandbox and replaces
    the vulnerable line with the fixed version.
    """

    filepath = hit["file"]

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Replace the vulnerable line with the fix
        target_line = hit["line_number"] - 1  # lists start at 0
        original = lines[target_line]
        lines[target_line] = fixed_code + "\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(
            f"   ✓ Fix applied to {os.path.basename(filepath)} line {hit['line_number']}"
        )
        return True

    except Exception as e:
        print(f"   ✗ Could not apply fix: {e}")
        return False


# ─────────────────────────────────────────
# PART 5 — MAIN FUNCTION
# ─────────────────────────────────────────


def run_coder_agent(repo_url, threat_report_path="threat_report.json"):
    """
    Main entry point for the Coder Agent.
    Reads threat report, clones repo, scans, fixes, saves report.
    """

    print("\n🛠  Coder Agent starting...")

    # Load the threat report from researcher
    with open(threat_report_path, "r") as f:
        threat_report = json.load(f)

    if not threat_report:
        print("✓ No threats to fix — exiting")
        return

    print(f"   Loaded {len(threat_report)} known vulnerabilities")

    # Step 1 — Clone into sandbox
    sandbox_dir = clone_to_sandbox(repo_url)
    if not sandbox_dir:
        return

    # Step 2 — Scan for vulnerable patterns
    hits = scan_sandbox_for_vulnerabilities(sandbox_dir, threat_report)

    if not hits:
        print("\n✓ No vulnerable patterns found in this repo")
        shutil.rmtree(sandbox_dir)
        return

    # Step 3 — Fix each hit
    fix_report = []

    print(f"\n🔧 Fixing {len(hits)} vulnerabilities...\n")

    for hit in hits:
        print(f"→ Fixing: {hit['pattern_matched']} in {os.path.basename(hit['file'])}")

        fixed_code = fix_vulnerability_with_gemini(hit)

        if fixed_code:
            success = apply_fix_to_file(hit, fixed_code)

            fix_report.append(
                {
                    "file": hit["file"],
                    "line_number": hit["line_number"],
                    "original_code": hit["line_content"],
                    "fixed_code": fixed_code,
                    "vulnerability": hit["description"],
                    "severity": hit["severity"],
                    "status": "FIXED" if success else "FAILED",
                }
            )

    # Step 4 — Save the fix report
    with open("fix_report.json", "w") as f:
        json.dump(fix_report, f, indent=2)

    # Step 5 — Print summary
    print("\n" + "─" * 50)
    print(f"✓ Coder Agent done!")
    print(f"  Sandbox location : {sandbox_dir}")
    print(f"  Vulnerabilities  : {len(hits)} found")
    fixed_count = sum(1 for r in fix_report if r["status"] == "FIXED")
    print(f"  Successfully fixed: {fixed_count}/{len(hits)}")
    print(f"  Report saved     : fix_report.json")
    print("─" * 50)

    return {"sandbox_dir": sandbox_dir, "fix_report": fix_report}


# ─────────────────────────────────────────
# TEST IT
# ─────────────────────────────────────────

if __name__ == "__main__":

    # Put any public Python repo here to test
    TEST_REPO = "https://github.com/mitsuhiko/flask"

    result = run_coder_agent(TEST_REPO)
