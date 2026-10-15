#!/usr/bin/env python3
"""Read-only health record after the isolated VM's offline upgrade."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import apt

if os.uname().nodename != "pardus-update-lab":
    raise SystemExit("This check requires the isolated pardus-update-lab VM")

print(datetime.now(timezone.utc).isoformat(), flush=True)
print(Path("/etc/os-release").read_text(), flush=True)
for command in (
    ["uname", "-r"],
    ["dpkg", "--audit"],
    ["dpkg-query", "-W", "pardus-update", "pardus-xfce-desktop", "python3-apt"],
    ["systemctl", "is-system-running"],
    ["systemctl", "--failed", "--no-pager", "--plain"],
    ["journalctl", "-b", "-p", "err", "--no-pager", "-n", "60"],
):
    result = subprocess.run(command, text=True, capture_output=True)
    print("COMMAND", json.dumps(command), "EXIT", result.returncode, flush=True)
    print(result.stdout + result.stderr, flush=True)

cache = apt.Cache()
print("broken_count:", cache.broken_count, flush=True)
cache.upgrade(dist_upgrade=True)
changes = cache.get_changes()
print("pending_changes:", len(changes), flush=True)
print(json.dumps([package.name for package in changes], ensure_ascii=False), flush=True)
print("system-update exists:", os.path.lexists("/system-update"), flush=True)

for relative in ("src/MainWindow.py", "src/PackageOperation.py", "src/SysActions.py"):
    path = Path("/usr/share/pardus/pardus-update") / relative
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "ABSENT"
    print("SHA256", relative, digest, flush=True)
