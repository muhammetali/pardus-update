#!/usr/bin/env python3
"""Check installed helper exclusion while the disposable VM's prepare is paused."""
import json
import os
from pathlib import Path
import stat
import subprocess

assert os.uname().nodename == "pardus-update-lab"
out = Path.home() / "update-lab/after"
pid = int((out / "paused-pid").read_text())
assert "T (stopped)" in Path(f"/proc/{pid}/status").read_text()
assert b"distupgradeoffline" in Path(f"/proc/{pid}/cmdline").read_bytes()
lock = Path("/run/pardus-update.lock")
assert stat.S_IMODE(lock.stat().st_mode) == 0o600
try:
    lock.open("r")
except PermissionError:
    print("Unprivileged lock access: denied")
else:
    raise AssertionError("Unprivileged process could open the root lock")

def archives():
    return {p.name: p.stat().st_size for p in Path("/var/cache/apt/archives").glob("*.deb")}

before = archives()
assert before
src = Path("/usr/share/pardus/pardus-update/src")
sources = Path("/etc/apt/sources.list").read_text()
assert "yirmibes" in sources
commands = [
    [str(src / "SysActions.py"), "controldistupgrade", sources],
    [str(src / "AutoAptUpdate.py")],
    [str(src / "AptSourceActions.py"), "fixsources", sources, "1", "1", "1", "1"],
]
rows = []
for command in commands:
    result = subprocess.run(["sudo", *command], text=True, capture_output=True, timeout=20)
    row = {"helper": Path(command[0]).name, "exit": result.returncode,
           "stdout": result.stdout, "stderr": result.stderr,
           "archives_unchanged": archives() == before}
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    assert result.returncode == 11, row
    assert row["archives_unchanged"], row
(out / "helper-exclusion.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
print(f"All three helpers rejected; {len(before)} archives preserved")
