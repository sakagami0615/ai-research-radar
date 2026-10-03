from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any


def capture_provenance(repo: Path, configs: dict[str, Any]) -> dict[str, Any]:
    safe = {key: (re.sub(r"https?://[^/\s:]+:[^@\s]+@", "https://redacted@", value) if isinstance(value, str) else value) for key, value in configs.items() if "key" not in key.lower() and "token" not in key.lower() and "password" not in key.lower()}
    text = repr(safe)
    safe_text = re.sub(r"https?://[^/\s:]+:[^@\s]+@", "https://redacted@", text)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    try:
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
        dirty: bool | None = bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        dirty = None
    return {"git_revision": commit, "dirty": dirty, "configs": safe, "config_hash": hashlib.sha256(safe_text.encode()).hexdigest()}
