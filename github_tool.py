import os
import re
import shutil
from git import Repo, GitCommandError
from dotenv import load_dotenv

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────

load_dotenv()

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox")


# ─────────────────────────────────────────
# PART 1 — CLONE REPO
# ─────────────────────────────────────────


def clone_repo(repo_url):
    """
    Clones the target repo into the local sandbox/ directory.
    If sandbox/ already exists from a previous run, it is deleted first
    to guarantee a clean state — this prevents the retry clone crash.

    Returns sandbox_dir path, or None on failure.
    """
    print(f"\n📦 GitHub Tool — Cloning repo...")
    print(f"   URL     : {repo_url}")
    print(f"   Target  : {SANDBOX_DIR}")

    # Clean up any previous run
    if os.path.exists(SANDBOX_DIR):
        print(f"   ○ Existing sandbox found — removing for clean state")
        shutil.rmtree(SANDBOX_DIR)

    os.makedirs(SANDBOX_DIR, exist_ok=True)

    try:
        Repo.clone_from(repo_url, SANDBOX_DIR)
        print(f"   ✓ Clone successful")
        return SANDBOX_DIR

    except GitCommandError as e:
        print(f"   ✗ Clone failed: {e}")
        return None

    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return None


# ─────────────────────────────────────────
# PART 2 — READ DEPENDENCIES FROM LOCAL CLONE
# ─────────────────────────────────────────


def get_dependencies(sandbox_dir):
    """
    Reads dependency files from the locally cloned repo.
    Checks in order: requirements.txt → setup.py → pyproject.toml

    Returns {"type": "python", "packages": [...]}
    """
    print(f"\n🔎 GitHub Tool — Reading dependencies from local clone...")

    packages = []

    # ── requirements.txt ──
    req_path = os.path.join(sandbox_dir, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, encoding="utf-8", errors="ignore") as f:
            packages = _parse_requirements(f.read())
        print(f"   ✓ requirements.txt → {len(packages)} packages")

    # ── setup.py ──
    if not packages:
        setup_path = os.path.join(sandbox_dir, "setup.py")
        if os.path.exists(setup_path):
            with open(setup_path, encoding="utf-8", errors="ignore") as f:
                packages = _parse_setup_py(f.read())
            print(f"   ✓ setup.py → {len(packages)} packages")

    # ── pyproject.toml ──
    if not packages:
        pyproject_path = os.path.join(sandbox_dir, "pyproject.toml")
        if os.path.exists(pyproject_path):
            with open(pyproject_path, encoding="utf-8", errors="ignore") as f:
                packages = _parse_pyproject(f.read())
            print(f"   ✓ pyproject.toml → {len(packages)} packages")

    # ── Fallback ──
    if not packages:
        print("   ○ No dependency file found — using common web packages as fallback")
        packages = ["Flask", "Django", "requests", "PyJWT", "SQLAlchemy"]

    print(f"   Packages: {packages}")
    return {"type": "python", "packages": packages}


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────


def _parse_requirements(content):
    packages = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[>=<!;\[]", line)[0].strip()
        if name:
            packages.append(name)
    return packages


def _parse_setup_py(content):
    packages = []
    match = re.search(r"install_requires\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
    if match:
        for item in re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)):
            name = re.split(r"[>=<!;]", item)[0].strip()
            if name:
                packages.append(name)
    return packages


def _parse_pyproject(content):
    packages = []
    match = re.search(r"dependencies\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
    if match:
        for item in re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)):
            name = re.split(r"[>=<!;\[]", item)[0].strip()
            if name and not name.startswith("python"):
                packages.append(name)
    return packages


# ─────────────────────────────────────────
# TEST IT
# ─────────────────────────────────────────

if __name__ == "__main__":
    sandbox = clone_repo("https://github.com/erev0s/VAmPI")
    if sandbox:
        deps = get_dependencies(sandbox)
        print(f"\nResult: {deps}")
