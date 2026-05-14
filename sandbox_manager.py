"""
sandbox_manager.py — Docker Sandboxing Layer
---------------------------------------------
Runs untrusted fixed code inside a restricted Docker container.

Security constraints enforced:
  - No network access (--network none)
  - Read-only filesystem except /tmp
  - Memory cap: 128MB
  - CPU cap: 50% of one core
  - Execution timeout: 30s
  - Runs as non-root user (nobody)
"""

import os
import shutil
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DOCKERFILE_PATH = Path(__file__).parent / "Dockerfile"
IMAGE_NAME = "agentic-sandbox:latest"

DEFAULT_TIMEOUT_SECONDS = 30
MAX_MEMORY = "128m"
CPU_QUOTA = "50000"


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def success(self):
        return self.exit_code == 0 and not self.timed_out


class SandboxManager:

    def __init__(self, image_name=IMAGE_NAME, timeout=DEFAULT_TIMEOUT_SECONDS):
        self.image_name = image_name
        self.timeout = timeout
        self._image_built = False

    # ── Public API ────────────────────────────────────────────────────────────

    def build_image(self, force=False):
        if self._image_built and not force:
            return True

        if not DOCKERFILE_PATH.exists():
            log.error(f"Dockerfile not found at {DOCKERFILE_PATH}")
            return False

        log.info(f"Building Docker image '{self.image_name}' ...")
        result = subprocess.run(
            ["docker", "build", "-t", self.image_name, "-f", str(DOCKERFILE_PATH), "."],
            capture_output=True,
            text=True,
            cwd=str(DOCKERFILE_PATH.parent),
        )

        if result.returncode != 0:
            log.error(f"Docker build failed:\n{result.stderr}")
            return False

        log.info("Docker image built successfully.")
        self._image_built = True
        return True

    def run(self, code_path, entry_file="test_fix.py", extra_files=None):
        """
        Copy code into a temp directory and run pytest inside Docker.

        Uses 'pytest -v' instead of 'python' to guarantee:
          - Tests are actually discovered and executed
          - Exit code is non-zero if any test fails
          - stdout contains "collected X items" for QA agent to verify
        """
        if not self._docker_available():
            return SandboxResult(
                exit_code=1, stdout="", stderr="Docker is not available.",
                error="docker_unavailable",
            )

        if not self.build_image():
            return SandboxResult(
                exit_code=1, stdout="", stderr="Failed to build sandbox image.",
                error="image_build_failed",
            )

        with tempfile.TemporaryDirectory(prefix="sandbox_") as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()

            self._copy_to_workspace(Path(code_path), workspace, extra_files)

            if not (workspace / entry_file).exists():
                return SandboxResult(
                    exit_code=1, stdout="",
                    stderr=f"Entry file '{entry_file}' not found in workspace.",
                    error="entry_not_found",
                )

            return self._run_container(str(workspace), entry_file)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _run_container(self, workspace_path, entry_file):
        cmd = [
            "docker", "run",
            "--rm",
            "--network", "none",           # no internet
            "--memory", MAX_MEMORY,        # RAM cap
            "--cpu-quota", CPU_QUOTA,      # CPU cap
            "--read-only",                 # read-only filesystem
            "--tmpfs", "/tmp:size=32m",    # writable tmp only
            "--user", "nobody",            # non-root
            "-v", f"{workspace_path}:/workspace:ro",
            "--workdir", "/workspace",
            self.image_name,
            # ── KEY FIX ──────────────────────────────────────────────────────
            # Using 'pytest -v' instead of 'python' ensures:
            #   1. Tests are actually discovered and executed
            #   2. Exit code != 0 if any test fails (python would exit 0)
            #   3. stdout contains "collected X items" for QA verification
            "pytest", "-v", entry_file,
        ]

        log.info(f"Launching container: pytest -v {entry_file}")
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
            )
            return SandboxResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            log.warning("Container execution timed out.")
            return SandboxResult(
                exit_code=124, stdout="",
                stderr=f"Execution timed out after {self.timeout}s.",
                timed_out=True,
            )
        except FileNotFoundError:
            return SandboxResult(
                exit_code=1, stdout="",
                stderr="'docker' command not found. Is Docker installed?",
                error="docker_not_found",
            )

    @staticmethod
    def _copy_to_workspace(src, workspace, extra_files=None):
        for f in src.glob("*.py"):
            shutil.copy2(f, workspace / f.name)
        if extra_files:
            for ef in extra_files:
                ep = Path(ef)
                if ep.exists():
                    shutil.copy2(ep, workspace / ep.name)

    @staticmethod
    def _docker_available():
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
