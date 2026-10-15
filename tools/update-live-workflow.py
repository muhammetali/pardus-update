#!/usr/bin/env python3
"""Destructive upgrade experiment: use ONLY in the disposable pardus-update-lab VM.

Runs the installed application and its real helpers. SIGSTOP holds the prepare
helper after it writes the new sources, so settings/home navigation is repeatable.
No package calculations, downloads, or helper commands are mocked. The baseline
run remains paused for inspection; restore its VM snapshot afterwards.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if os.uname().nodename != "pardus-update-lab":
    raise SystemExit("This experiment requires the disposable pardus-update-lab VM")
mode = sys.argv[1]
assert mode in ("before", "after")
mirror = sys.argv[2] if len(sys.argv) > 2 else None
out = Path.home() / "update-lab" / mode
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/usr/share/pardus/pardus-update/src")
from MainWindow import MainWindow
from gi.repository import Gtk, GLib, Gio, Gdk

events = []
def record(event, **data):
    row = {"event": event, "time": time.time(), **data}
    events.append(row)
    print("LAB " + json.dumps(row, ensure_ascii=False), flush=True)
    (out / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2))

def archives():
    files = sorted(Path("/var/cache/apt/archives").glob("*.deb"))
    return {"count": len(files), "bytes": sum(f.stat().st_size for f in files),
            "names": [f.name for f in files]}

def screenshot(name):
    root = Gdk.get_default_root_window()
    pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
    pixbuf.savev(str(out / (name + ".png")), "png", [], [])

app = Gtk.Application(application_id="tr.org.pardus.updatelab", flags=Gio.ApplicationFlags.NON_UNIQUE)
app.register(None)
app.args = {}
w = MainWindow(app)
control_pids = []
prepare_pid = None
original_control = w.startControlDistUpgradeProcess
original_prepare = w.startDistUpgradeProcess
original_download_done = w.distupgrade_vte_on_done

def control(params):
    pid = original_control(params)
    control_pids.append(pid)
    record("control_started", pid=pid, command=params)
    return pid

def prepare(params):
    global prepare_pid
    prepare_pid = original_prepare(params)
    record("prepare_started", pid=prepare_pid, command=params)
    return prepare_pid

w.startControlDistUpgradeProcess = control
w.startDistUpgradeProcess = prepare

def download_done(terminal, status):
    text = terminal.get_text()[0]
    (out / f"download-{download_attempts}.log").write_text(text or "")
    record("download_exit", status=status)
    original_download_done(terminal, status)

w.distupgrade_vte_on_done = download_done
home = next(o for o in w.GtkBuilder.get_objects()
            if isinstance(o, Gtk.Button) and o.get_name() == "homecontrol")
settings = w.GtkBuilder.get_object("ui_menusettings_button")
phase = "startup"
started = time.monotonic()
phase_time = started
download_attempts = 0

def tick():
    global phase, phase_time, download_attempts
    page = w.ui_distupgrade_stack.get_visible_child_name()
    if time.monotonic() - started > 1800:
        record("timeout", phase=phase, page=page)
        Gtk.main_quit()
        return False
    if phase == "startup" and w.dist_upgradable and not w.update_inprogress:
        record("startup_complete", distro=w.user_distro_version, target=w.dist_new_version)
        if mirror:
            w.dist_new_sources = w.dist_new_sources.replace("http://depo.pardus.org.tr", mirror.rstrip("/"))
            record("official_mirror_selected", mirror=mirror, sources=w.dist_new_sources)
        home.emit("clicked")
        phase = "control"
    elif phase == "control" and page == "distupdateinfo" and not w.upgrade_inprogress:
        record("plan_ready")
        phase = "plan_visible"
        phase_time = time.monotonic()
    elif phase == "plan_visible" and time.monotonic() - phase_time > 0.5:
        screenshot("01-plan")
        w.ui_distuptodown_button.emit("clicked")
        download_attempts += 1
        phase = "download"
    elif phase == "download" and not w.upgrade_inprogress:
        if page == "install":
            snapshot = archives()
            (out / "archives-before.json").write_text(json.dumps(snapshot, indent=2))
            record("download_complete", count=snapshot["count"], bytes=snapshot["bytes"])
            phase = "downloaded_visible"
            phase_time = time.monotonic()
        elif w.ui_distuptodownretry_button.get_visible() and download_attempts < 3:
            record("download_retry", attempt=download_attempts)
            w.ui_distuptodownretry_button.emit("clicked")
            download_attempts += 1
        else:
            record("download_failed", page=page)
            screenshot("download-failed")
            Gtk.main_quit()
            return False
    elif phase == "downloaded_visible" and time.monotonic() - phase_time > 0.5:
        screenshot("02-downloaded")
        w.ui_distupgrade_button.emit("clicked")
        phase = "prepare"
    elif phase == "prepare" and "yirmibes" in Path("/etc/apt/sources.list").read_text():
        # Pause only the helper, after real preparation has begun. Its apt-update
        # child can finish; the helper cannot reach the reboot request yet.
        subprocess.run(["sudo", "kill", "-STOP", str(prepare_pid)], check=True)
        record("prepare_paused", pid=prepare_pid,
               cmdline=Path(f"/proc/{prepare_pid}/cmdline").read_bytes().replace(b"\0", b" ").decode())
        phase = "preparing_visible"
        phase_time = time.monotonic()
    elif phase == "preparing_visible" and time.monotonic() - phase_time > 0.5:
        screenshot("03-preparing")
        settings.emit("clicked")
        settings.emit("clicked")
        home.emit("clicked")
        phase = "observe"
        phase_time = time.monotonic()
    elif phase == "observe" and time.monotonic() - phase_time > 8:
        snapshot = archives()
        (out / "archives-after.json").write_text(json.dumps(snapshot, indent=2))
        record("after_navigation", control_requests=len(control_pids),
               page=w.ui_distupgrade_stack.get_visible_child_name(),
               main_page=w.ui_main_stack.get_visible_child_name(),
               busy=w.upgrade_inprogress, count=snapshot["count"], bytes=snapshot["bytes"])
        screenshot("04-after-navigation")
        (out / "paused-pid").write_text(str(prepare_pid))
        # Host orchestrator inspects the result before resuming the patched run.
        phase = "inspection"
    return True

GLib.timeout_add(100, tick)
Gtk.main()
