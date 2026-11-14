#!/usr/bin/env python3
"""Ejects a mounted floppy from the File menu, as a user would, on a Macintosh IIfx
or SE/30.

    tools/headless.sh python3 tools/guitest/eject.py --rom ROM --floppy SYSTEM-DISK
        [--model iifx|se30] [--video-rom FILE] [--boot-seconds N] [--app FILE] [--shots DIR]

The machine starts from a copy of the floppy (unlocked). Once the Finder is up the
test picks File > Eject Floppy from Internal Drive and checks that

  - the Macintosh itself ejects the disk: the drive empties within eight
    seconds (the core gives up after that and pulls the disk). The IIfx's
    floppy processor takes at least half a second, so at once would be the disk
    pulled out from under the System; on the SE/30 the File Manager's own
    results for the flush and the eject are in the log and must both be 0,
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
ap.add_argument("--model", default="iifx", choices=["iifx", "se30"])
ap.add_argument("--video-rom", help="the SE/30's real video ROM file (without it: OpenMac's own)")
ap.add_argument("--boot-seconds", type=int, default=120, help="time given to reach the Finder")
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
ap.add_argument("--shots", default=None, help="folder for a screenshot of each step")
args = ap.parse_args()
for need in (args.rom, args.floppy, args.app) + ((args.video_rom,) if args.video_rom else ()):
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

# Per machine: its name, the settings' suffix, the log's lines for a disk put
# in, an eject handed to the Macintosh, and the drive found empty afterwards,
# and the least time the Macintosh's own eject takes.
NAME, SUFFIX, PUT_IN, ASKED, EJECTED, SOONEST = {
    "iifx": ("IIfx", "Iifx", r"IIfx SuperDrive: ", r"\[core\] floppy: the Macintosh was asked to eject the disk",
             r"\[disk\] the IIfx ejected ", 0.5),
    "se30": ("SE/30", "Se30", r"\[core\] Macintosh SE/30 floppy: ",
             r"\[core\] floppy: the host's Eject asked the File Manager \(flush (-?\d+), eject (-?\d+)\)",
             r"\[disk\] the machine ejected ", 0.0),
}[args.model]
settings = {"Model": args.model, "Scale": 1, "LastRom" + SUFFIX: os.path.abspath(args.rom), "LastFloppy" + SUFFIX: floppy,
            "RamMB" + SUFFIX: 8, "WriteProtectFloppies": False, "ExternalDrive": False}
if args.video_rom: settings["VideoRomSe30"] = os.path.abspath(args.video_rom)
with open(os.path.join(profile, "settings.json"), "w") as f:
    json.dump(settings, f)
if os.path.exists(log_path): os.remove(log_path)
app = subprocess.Popen([args.app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    check(wait_log(r"display: first guest frame shown") is not None, f"the {NAME} starts in the window")
    name = re.escape(os.path.basename(floppy))
    check(wait_log(PUT_IN + name, 10) is not None, "the floppy is in the drive")
    seated = wait_log(r"\[core\] floppy: [^\n]* disk in the internal SuperDrive \(([^)\n]*)\)", 10)
    check(seated is not None and "write-protected" not in seated.group(1), "and it is not write-protected")
    print(f"        waiting {args.boot_seconds} s for the Finder")
    time.sleep(args.boot_seconds)
    shot("1-finder")
    check(app.poll() is None, "the app is still running")
    check(re.search(EJECTED, log_text()) is None, "nothing has ejected the disk so far (the control)")

    menu = open_file_menu()
    check(menu is not None, "the File menu opens")
    if menu:
        shot("2-file-menu")
        mark = len(log_text())
        clicked = time.time()
        click(menu[1] + 120, menu[2] + row_y("Eject Floppy from Internal Drive"))
        asked = wait_log(ASKED, 5, mark)
        check(asked is not None, "the eject is handed to the Macintosh")
        if asked and asked.groups():
            check(asked.groups() == ("0", "0"),
                  f"its File Manager flushed and ejected the volume (results {asked.group(1)} and {asked.group(2)})")
        out = wait_log(EJECTED + name, 14, mark)
        took = time.time() - clicked - 1.08          # click() itself sleeps that long after the press
        check(out is not None, "the drive empties")
        if out:
            check(SOONEST <= took < 8.0,
                  f"the Macintosh ejected it itself, {max(took, 0.0):.1f} s after the click ({SOONEST:g} to 8 s)")
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
            check(re.search(ASKED, log_text()[mark:]) is None, "with the drive empty the menu entry does nothing")
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
