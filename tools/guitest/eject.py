#!/usr/bin/env python3
"""Ejects a mounted floppy from the File menu, as a user would, on a Macintosh IIfx.

    tools/headless.sh python3 tools/guitest/eject.py --rom IIFX.ROM --floppy SYSTEM-DISK
        [--boot-seconds N] [--app FILE] [--shots DIR]

The IIfx starts from a copy of the floppy (unlocked). Once the Finder is up the
test picks File > Eject Floppy from Internal Drive and checks that

  - the Macintosh itself ejects the disk: the drive empties between half a
    second and eight seconds later (at once would be the disk pulled out from
    under the System; ten seconds is the core's give-up time),
  - the disk's file is written back, changed and still a Macintosh volume,
  - the menu entry is switched off again and the log holds no error.

Needs python-xlib.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from Xlib import X, display
from Xlib.ext import xtest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--rom", required=True)
ap.add_argument("--floppy", required=True)
ap.add_argument("--boot-seconds", type=int, default=120, help="time given to reach the Finder")
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
ap.add_argument("--shots", default=None, help="folder for a screenshot of each step")
args = ap.parse_args()
for need in (args.rom, args.floppy, args.app):
    if not os.path.exists(need):
        sys.exit(f"eject test: missing {need}")
config = os.environ.get("XDG_CONFIG_HOME")
if not config or os.path.realpath(config).startswith(os.path.realpath(os.path.expanduser("~/.config"))):
    sys.exit("eject test: refusing to run outside tools/headless.sh (it would use the real profile)")
profile = os.path.join(config, "OpenMac")
os.makedirs(profile, exist_ok=True)
log_path = os.path.join(profile, "openmac.log")
floppy = os.path.join(profile, os.path.basename(args.floppy))
shutil.copyfile(args.floppy, floppy)
original = open(floppy, "rb").read()

failures = []
def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok: failures.append(what)

def log_text():
    try:
        with open(log_path, errors="replace") as f: return f.read()
    except FileNotFoundError:
        return ""

def wait_log(pattern, timeout=30.0, start=0):
    end = time.time() + timeout
    while time.time() < end:
        m = re.search(pattern, log_text()[start:])
        if m: return m
        time.sleep(0.05)
    return None

def shot(name):
    if not args.shots: return
    os.makedirs(args.shots, exist_ok=True)
    subprocess.run(["import", "-window", "root", os.path.join(args.shots, name + ".png")], stderr=subprocess.DEVNULL)

d = display.Display()
root = d.screen().root

def windows():
    out = []
    for w in root.query_tree().children:
        try:
            if w.get_attributes().map_state != X.IsViewable: continue
            g = w.get_geometry()
            out.append((w.id, g.x, g.y, g.width, g.height))
        except Exception:
            pass
    return out

def click(x, y):
    xtest.fake_input(d, X.MotionNotify, x=x, y=y); d.sync(); time.sleep(0.3)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.08)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync(); time.sleep(0.7)

def main_window():
    m = re.search(r"window: platform handle XID 0x([0-9A-Fa-f]+)", log_text())
    wid = int(m.group(1), 16) if m else None
    for w in windows():
        if w[0] == wid: return w
    return None

# The File menu's rows, top to bottom; a separator is thinner than an entry.
ROW, SEPARATOR, FIRST = 27, 9, 17
FILE_MENU = ["Open ROM", "Open Recent", None, "Write-Protect Floppies", "Insert Floppy in Internal Drive",
             "Eject Floppy from Internal Drive"]
def row_y(name):
    y = FIRST
    for entry in FILE_MENU:
        if entry == name: return y
        y += SEPARATOR if entry is None else ROW
    raise KeyError(name)

def open_file_menu():
    w = main_window()
    before = {x[0] for x in windows()}
    click(w[1] + 22, w[2] + 16)
    menus = [x for x in windows() if x[0] not in before]
    return menus[0] if len(menus) == 1 else None

with open(os.path.join(profile, "settings.json"), "w") as f:
    json.dump({"Model": "iifx", "Scale": 1, "LastRomIifx": os.path.abspath(args.rom), "LastFloppyIifx": floppy,
               "RamMBIifx": 8, "WriteProtectFloppies": False, "ExternalDrive": False}, f)
if os.path.exists(log_path): os.remove(log_path)
app = subprocess.Popen([args.app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    check(wait_log(r"display: first guest frame shown") is not None, "the IIfx starts in the window")
    name = re.escape(os.path.basename(floppy))
    check(wait_log(r"IIfx SuperDrive: " + name, 10) is not None, "the floppy is in the drive")
    seated = wait_log(r"\[core\] floppy: [^\n]* disk in the internal SuperDrive \(([^)\n]*)\)", 10)
    check(seated is not None and "write-protected" not in seated.group(1), "and it is not write-protected")
    print(f"        waiting {args.boot_seconds} s for the Finder")
    time.sleep(args.boot_seconds)
    shot("1-finder")
    check(app.poll() is None, "the app is still running")
    check(re.search(r"the IIfx ejected", log_text()) is None, "nothing has ejected the disk so far (the control)")

    menu = open_file_menu()
    check(menu is not None, "the File menu opens")
    if menu:
        shot("2-file-menu")
        mark = len(log_text())
        clicked = time.time()
        click(menu[1] + 120, menu[2] + row_y("Eject Floppy from Internal Drive"))
        asked = wait_log(r"\[core\] floppy: the Macintosh was asked to eject the disk", 5, mark)
        check(asked is not None, "the eject is handed to the Macintosh")
        out = wait_log(r"\[disk\] the IIfx ejected " + name, 14, mark)
        took = time.time() - clicked - 1.08          # click() itself sleeps that long after the press
        check(out is not None, "the drive empties")
        if out:
            check(0.5 <= took < 8.0, f"the Macintosh ejected it itself, {took:.1f} s after the click (0.5 to 8 s)")
        log = log_text()[mark:]
        check("did not eject the disk" not in log, "the core did not have to take the disk out")
        check("disk ejected from the internal SuperDrive" in log, "the mechanism reports the eject")
        time.sleep(1.5)
        shot("3-ejected")
        written = open(floppy, "rb").read()
        changed = sum(1 for i in range(0, min(len(written), len(original)), 512) if written[i:i+512] != original[i:i+512])
        body = written[84:] if len(written) == 1474560 + 84 else written     # a DiskCopy 4.2 file has an 84-byte header
        check(len(written) == len(original) and body[1024:1026] == b"BD" and 0 < changed < 400,
              f"the disk's file was written back: same size, still a Macintosh volume, {changed} sectors changed")
        menu = open_file_menu()
        if menu:
            shot("4-file-menu-after")
            mark = len(log_text())
            click(menu[1] + 120, menu[2] + row_y("Eject Floppy from Internal Drive"))
            time.sleep(1.0)
            check("asked to eject" not in log_text()[mark:], "with the drive empty the menu entry does nothing")
            xtest.fake_input(d, X.KeyPress, 9); d.sync(); xtest.fake_input(d, X.KeyRelease, 9); d.sync()   # Escape
    check(app.poll() is None, "the app is still running at the end")
finally:
    app.terminate()
    try: app.wait(10)
    except subprocess.TimeoutExpired: app.kill()

log = log_text()
bad = [l for l in log.splitlines() if re.search(r"UNHANDLED|FATAL|frame tick failed|load failed|could not|write-back failed", l)]
check(not bad, "no errors in the app's log" + (": " + bad[0][:160] if bad else ""))
for line in log.splitlines():
    if re.search(r"\[disk\]|SuperDrive|floppy", line) and "[core] boot f=" not in line:
        print("        " + line[25:185])
print("EJECT TEST " + ("PASSED" if not failures else f"FAILED ({len(failures)})"))
sys.exit(1 if failures else 0)
