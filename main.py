import os
import json
from github_tool import clone_repo, get_dependencies
from researcher import run_researcher_agent
from coder import run_coder_agent
from qa import run_qa_agent

# pr_agent is YOUR file that uses PyGithub
# It must expose: run_pr_agent(repo_url, files_to_push)
# where files_to_push = [{"file_path": "relative/path.py", "new_code": "full file content"}, ...]
from pr_agent import run_pr_agent

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────

TARGET_REPO = "https://github.com/MartinAshraf/VAmPI"
MAX_RETRIES = 3

# ═════════════════════════════════════════
# STEP 1 — CLONE (happens ONCE, before everything)
# ═════════════════════════════════════════
# github_tool handles cleanup of any previous sandbox/
# so retrying the whole pipeline never causes a clone crash.

print("=" * 55)
print("STEP 1 — CLONE REPO")
print("=" * 55)

sandbox_dir = clone_repo(TARGET_REPO)

if not sandbox_dir:
    print("✗ Clone failed — aborting pipeline")
    exit(1)

print(f"\n✓ Repo cloned → {sandbox_dir}")

# ═════════════════════════════════════════
# STEP 2 — READ DEPENDENCIES FROM LOCAL CLONE
# ═════════════════════════════════════════
# We read from the local files, not from the GitHub API,
# so we get exactly what this version of the repo declares.

print("\n" + "=" * 55)
print("STEP 2 — READ DEPENDENCIES")
print("=" * 55)

dependencies = get_dependencies(sandbox_dir)
print(f"\n✓ Dependencies ready: {dependencies['packages']}")

# ═════════════════════════════════════════
# STEP 3 — RESEARCHER
# ═════════════════════════════════════════

print("\n" + "=" * 55)
print("STEP 3 — RESEARCHER AGENT")
print("=" * 55)

threat_report = run_researcher_agent(dependencies)

with open("threat_report.json", "w") as f:
    json.dump(threat_report, f, indent=2)

print("\n✓ Researcher done — threat_report.json saved")

if not threat_report:
    print("✓ No threats found — pipeline complete")
    exit(0)

# ═════════════════════════════════════════
# STEP 4+5 — CODER → QA LOOP
# ═════════════════════════════════════════
# Architecture notes:
#   - sandbox_dir is passed in; Coder does NOT clone
#   - On retry, same sandbox_dir is reused (files already on disk)
#   - previous_error carries QA failure context into Coder's self-critique

print("\n" + "=" * 55)
print("STEP 4+5 — CODER / QA LOOP")
print("=" * 55)

previous_error = None
coder_result = None
qa_result = None

for attempt in range(1, MAX_RETRIES + 1):

    print(f"\n── Attempt {attempt}/{MAX_RETRIES} " + "─" * 30)

    # ── Coder ────────────────────────────────────────────────────────────────
    coder_result = run_coder_agent(
        sandbox_dir=sandbox_dir,
        threat_report_path="threat_report.json",
        previous_error=previous_error,
    )

    if not coder_result:
        print("✗ Coder returned nothing — aborting")
        break

    test_file = coder_result.get("test_file_path")

    if not test_file:
        print("✗ No test file generated — aborting")
        break

    # ── QA ───────────────────────────────────────────────────────────────────
    qa_result = run_qa_agent(
        sandbox_dir=sandbox_dir,
        test_file_path=test_file,
    )

    if qa_result["passed"]:
        print(f"\n✅ QA PASSED on attempt {attempt}")
        break

    # ── Build error context for Coder's next self-critique ───────────────────
    print(f"\n❌ QA FAILED on attempt {attempt} — sending error back to Coder...")

    lines = [
        f"QA VERDICT : FAIL",
        f"SUMMARY    : {qa_result['summary']}",
    ]
    if qa_result.get("errors"):
        lines.append("ERRORS:")
        lines.extend(f"  - {e}" for e in qa_result["errors"][:5])
    if qa_result.get("suggestions"):
        lines.append("SUGGESTIONS:")
        lines.extend(f"  - {s}" for s in qa_result["suggestions"][:3])

    previous_error = "\n".join(lines)

    if attempt == MAX_RETRIES:
        print("\n⚠️  Max retries reached — could not pass QA")

# ═════════════════════════════════════════
# STEP 6 — PULL REQUEST
# ═════════════════════════════════════════
# pr_agent needs:
#   - repo_url : the original GitHub URL
#   - files_to_push : list of {file_path (relative), new_code (full file content)}
#
# We derive this by:
#   1. Taking each successfully fixed file path from fix_report
#   2. Making the path relative to sandbox_dir (repo root)
#   3. Reading the FULL current file content from disk
#      (not just the fixed line — PyGithub needs the entire file)

if qa_result and qa_result["passed"] and coder_result:

    print("\n" + "=" * 55)
    print("STEP 6 — PULL REQUEST")
    print("=" * 55)

    fix_report = coder_result["fix_report"]

    # Build the files_to_push list for pr_agent
    files_to_push = []
    for record in fix_report:
        if record["status"] != "FIXED":
            continue

        abs_path = record["file"]

        # Make path relative to repo root (what GitHub expects)
        relative_path = os.path.relpath(abs_path, sandbox_dir)

        # Read FULL file content — pr_agent needs this to update the file on GitHub
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                full_content = f.read()
        except Exception as e:
            print(f"   ✗ Could not read {relative_path}: {e}")
            continue

        files_to_push.append(
            {
                "file_path": relative_path,  # e.g. "app/views.py"
                "new_code": full_content,  # full updated file content
            }
        )

    if files_to_push:
        pr_result = run_pr_agent(
            repo_url=TARGET_REPO,
            files_to_push=files_to_push,
        )
        print(f"\n✓ PR opened: {pr_result.get('pr_url', 'N/A')}")
    else:
        print("   ○ No files to push")

else:
    print("\n⚠️  Skipping PR — QA did not pass")

# ═════════════════════════════════════════
# DONE
# ═════════════════════════════════════════

print("\n" + "=" * 55)
final = "PASS ✅" if (qa_result and qa_result["passed"]) else "FAIL ❌"
print(f"  Pipeline complete — {final}")
print(f"  fix_report.json saved")
print("=" * 55)
