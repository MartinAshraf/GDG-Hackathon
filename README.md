# 🛡️ Agentic Code Enhancer

> An autonomous multi-agent AI system that automatically detects, fixes, and tests security vulnerabilities in Python repositories.

Built for the **GDG Hackathon** — demonstrating a full Researcher → Coder → QA pipeline powered by Google Gemini.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [How the Sandbox Works](#how-the-sandbox-works)

---

## Overview

Traditional security tools find vulnerabilities — they don't fix them. This system goes further: it reads a target GitHub repository, identifies vulnerable code patterns, generates secure fixes using an LLM, writes adversarial tests to verify the fixes, and runs them inside an isolated Docker container.

If the tests fail, the system automatically retries — sending the error back to the Coder agent so it can **self-critique** and produce a better fix.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│                     (Orchestrator)                      │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────┐
│   researcher.py     │  Scrapes GitHub Security Advisories
│  (Researcher Agent) │  → Builds a threat report (JSON)
└──────────┬──────────┘
           │  threat_report.json
           ▼
┌─────────────────────┐
│     coder.py        │  Clones repo → Scans for patterns
│   (Coder Agent)     │  → Fixes vulnerabilities via Gemini
│                     │  → Generates adversarial test file
└──────────┬──────────┘
           │  fixed code + test_fix.py
           ▼
┌─────────────────────┐     ┌──────────────────────────┐
│      qa.py          │────▶│   sandbox_manager.py     │
│   (QA Agent)        │     │   (Docker Sandbox)       │
│                     │◀────│   pytest -v test_fix.py  │
└──────────┬──────────┘     └──────────────────────────┘
           │
     ┌─────┴──────┐
     │            │
   PASS          FAIL
     │            │
     ▼            ▼
  Done ✅    Send error back
             to Coder Agent
             (up to 3 retries)
```

---

## Features

| Feature | Details |
|---|---|
| **Autonomous Pipeline** | Researcher → Coder → QA, fully automated |
| **Multi-agent Debate** | On failure, Coder receives QA error and self-critiques before retrying |
| **Docker Sandboxing** | Fixed code runs in an isolated container with no network, no root, memory/CPU limits |
| **Prompt Injection Guard** | All agents have system prompts that reject instructions embedded in scanned code |
| **Adversarial Testing** | Gemini generates tests with a hostile QA persona, not just happy-path assertions |
| **JSON-guaranteed Output** | `response_mime_type="application/json"` prevents malformed LLM responses |
| **Graceful Fallback** | If Gemini API is down, QA falls back to heuristic (exit code 0 = pass) |

---

## Project Structure

```
agentic-code-enhancer/
│
├── main.py               # Orchestrator — runs the full pipeline
├── researcher.py         # Scrapes GitHub advisories + builds threat report
├── coder.py              # Clones repo, fixes vulnerabilities, generates tests
├── qa.py                 # Runs tests in Docker sandbox, analyses results
├── sandbox_manager.py    # Docker container management
│
├── Dockerfile            # Minimal Python 3.11 sandbox image
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .gitignore
│
├── threat_report.json    # Generated at runtime by researcher
├── fix_report.json       # Generated at runtime by coder
└── sandbox/              # Cloned repo lives here (git-ignored)
```

---

## Prerequisites

- Python 3.10+
- Docker Desktop (running)
- A Google Gemini API key ([get one here](https://aistudio.google.com/))

---

## Installation

**1. Clone this repository**

```bash
git clone https://github.com/your-username/agentic-code-enhancer.git
cd agentic-code-enhancer
```

**2. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**3. Build the Docker sandbox image**

This only needs to be done once.

```bash
docker build -t agentic-sandbox:latest -f Dockerfile .
```

---

## Configuration

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
GEMINI_API_KEY=your-gemini-api-key-here
```

---

## Usage

**Run the full pipeline:**

```bash
python main.py
```

The pipeline will:
1. Scrape GitHub Security Advisories for Flask, PyJWT, and requests
2. Clone the target repo (`VAmPI`) into a local `sandbox/` folder
3. Scan every Python file for vulnerable patterns
4. Fix each vulnerability using Gemini
5. Generate an adversarial `test_fix.py`
6. Run the tests inside Docker
7. Retry (up to 3 times) if tests fail

**Output files generated:**

| File | Contents |
|---|---|
| `threat_report.json` | Vulnerabilities found by the Researcher |
| `fix_report.json` | Each fix: original code, fixed code, status |
| `sandbox/test_fix.py` | Auto-generated adversarial test file |

---

## How the Sandbox Works

The Docker container enforces a **Zero-Trust** security model:

```
--network none        → No internet access
--read-only           → Filesystem is read-only
--memory 128m         → RAM capped at 128MB
--cpu-quota 50000     → Max 50% of one CPU core
--user nobody         → Runs as non-root (UID 65534)
--tmpfs /tmp:size=32m → Only /tmp is writable
```

The code directory is mounted as `:ro` (read-only), so the container **cannot modify the source files** even if the code tries to.

> **Production note:** The Dockerfile installs only `pytest`, `requests`, `Flask`, and `PyJWT` — the exact packages needed for the target repo. This minimises the attack surface. For other repos, add their dependencies to the Dockerfile before building.
