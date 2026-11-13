#!/usr/bin/env python3
"""A file dropped on the window rides in on its own disk; this checks both ways of
getting rid of that disk for good, on a Quadra 950.

    tools/headless.sh python3 tools/guitest/dropdisk.py --rom Q950.ROM --hard-disk SYSTEM.img
        --file BIG-FILE [--icon X,Y] [--trash X,Y] [--boot-seconds N] [--app FILE] [--shots DIR]

SYSTEM.img is a startup disk with Mac OS 8 (a copy is used); BIG-FILE is any file
over 1.3 MB, which is what becomes a disk on the second SCSI seat. --icon and
--trash are where the dropped disk's icon and the Trash sit on the Mac's 640x480
screen (defaults: second place in the right-hand column, and the bottom right).

  1. The Mac starts with the dropped disk on its desktop. Its icon is dragged to
     the Trash and the Finder's question is answered OK -> the app takes the disk
     off the seat, and after a reset it does not come back.
  2. The app starts again with the same file -> File > Remove Dropped Disk takes
     it off, and the icon leaves the Mac's desktop.

The icon's patch of the screen is compared between the steps: with the disk it
must differ from the patch without it (the control), and every "gone" patch
must be the same picture. Needs python-xlib and ImageMagick.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from Xlib import X, XK, display
from Xlib.ext import xtest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--rom", required=True)
ap.add_argument("--hard-disk", required=True)
ap.add_argument("--file", required=True)
ap.add_argument("--icon", default="591,115")
ap.add_argument("--trash", default="587,426")
ap.add_argument("--boot-seconds", type=int, default=100, help="time given to reach the Finder")
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
ap.add_argument("--shots", default=None, help="folder for a screenshot of each step")
args = ap.parse_args()
for need in (args.rom, args.hard_disk, args.file, args.app):
    if not os.path.exists(need):
        sys.exit(f"drop disk test: missing {need}")
if os.path.getsize(args.file) <= 1_300_000:
    sys.exit("drop disk test: --file must be over 1.3 MB (a smaller one rides on a floppy)")
config = os.environ.get("XDG_CONFIG_HOME")
if not config or os.path.realpath(config).startswith(os.path.realpath(os.path.expanduser("~/.config"))):
    sys.exit("drop disk test: refusing to run outside tools/headless.sh (it would use the real profile)")
ICON = tuple(int(v) for v in args.icon.split(","))
TRASH = tuple(int(v) for v in args.trash.split(","))
profile = os.path.join(config, "OpenMac")
os.makedirs(profile, exist_ok=True)
log_path = os.path.join(profile, "openmac.log")
disk = os.path.join(profile, "startup.img")
shutil.copyfile(args.hard_disk, disk)
label = os.path.basename(args.file)
with open(os.path.join(profile, "settings.json"), "w") as f:
    json.dump({"Model": "quadra950", "Scale": 1, "LastRomQuadra950": os.path.abspath(args.rom),
               "LastHardDiskQuadra950": disk, "RamMBQuadra950": 32, "ExternalDrive": False}, f)

failures = []
def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what, flush=True)
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

d = display.Display()
root = d.screen().root
shot_n = 0
def shot(name):
    global shot_n
    if not args.shots: return
    shot_n += 1
    os.makedirs(args.shots, exist_ok=True)
    subprocess.run(["import", "-window", "root", os.path.join(args.shots, f"{shot_n}-{name}.png")],
                   stderr=subprocess.DEVNULL)

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

def button(n, down):
    xtest.fake_input(d, X.ButtonPress if down else X.ButtonRelease, n); d.sync(); time.sleep(0.08)
def click(x, y):
    xtest.fake_input(d, X.MotionNotify, x=x, y=y); d.sync(); time.sleep(0.3)
    button(1, True); button(1, False); time.sleep(0.7)
def tap(name):
    code = d.keysym_to_keycode(XK.string_to_keysym(name))
    xtest.fake_input(d, X.KeyPress, code); d.sync(); time.sleep(0.06)
    xtest.fake_input(d, X.KeyRelease, code); d.sync(); time.sleep(0.06)
def move_by(dx, dy, step=1):
    """Relative motion one pixel at a time: slow enough that the Mac moves its
    pointer by what the mouse moved, with none of its own speeding up."""
    n = max(abs(dx), abs(dy)) // step or 1
    sx = sy = 0
    for i in range(1, n + 1):
        tx, ty = dx * i // n, dy * i // n
        xtest.fake_input(d, X.MotionNotify, detail=1, x=tx - sx, y=ty - sy); d.sync()
        sx, sy = tx, ty
        time.sleep(0.02)

def main_window():
    m = re.search(r"window: platform handle XID 0x([0-9A-Fa-f]+)", log_text())
    wid = int(m.group(1), 16) if m else None
    for w in windows():
        if w[0] == wid: return w
    return None

MENU_BAR = 32      # the app's own menu bar, above the Mac's screen
def icon_patch():
    """The picture of the dropped disk's place on the Mac's desktop (icon and name)."""
    w = main_window()
    x, y = w[1] + ICON[0] - 46, w[2] + MENU_BAR + ICON[1] - 22
    raw = subprocess.run(["import", "-window", "root", "-crop", f"92x52+{x}+{y}", "+repage", "rgb:-"],
                         capture_output=True).stdout
    return hashlib.sha256(raw).hexdigest()[:16] if raw else None

def desktop_drawn():
    """True when the Mac's screen holds a picture: a machine that never started
    shows one flat color, and two flat patches compare equal."""
    w = main_window()
    out = subprocess.run(["import", "-window", "root", "-crop", f"640x480+{w[1]}+{w[2] + MENU_BAR}", "+repage",
                          "-format", "%k", "info:"], capture_output=True, text=True).stdout.strip()
    return out.isdigit() and int(out) > 200

def open_menu(offset_x):
    w = main_window()
    before = {x[0] for x in windows()}
    click(w[1] + offset_x, w[2] + 16)
    menus = [x for x in windows() if x[0] not in before]
    return menus[0] if len(menus) == 1 else None

def capture():
    w = main_window()
    d.create_resource_object("window", w[0]).set_input_focus(X.RevertToParent, X.CurrentTime); d.sync()
    mark = len(log_text())
    click(w[1] + 320, w[2] + MENU_BAR + 440)          # the capturing click is not a Mac click
    return wait_log(r"input: capture engaged", 5, mark) is not None
def release():
    button(2, True); button(2, False); time.sleep(0.5)

def start(first):
    """Start the app with the file on its command line (the same road as a drop),
    say Yes to the restart that loads the seat's driver, wait for the Finder."""
    mark = len(log_text())
    app = subprocess.Popen([args.app, os.path.abspath(args.file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    built = wait_log(r"\[disk\] transfer disk built for " + re.escape(label), 40, mark)
    check(built is not None, "the file becomes a transfer disk")
    time.sleep(2.0)
    asks = [x for x in windows() if x[0] != (main_window() or (0,))[0] and x[3] > 300 and x[4] < 300]
    check(len(asks) == 1, "the app asks for the restart that loads the disk's driver")
    if asks:
        mark = len(log_text())
        click(asks[0][1] + asks[0][3] - 66, asks[0][2] + asks[0][4] - 35)      # Yes
        check(wait_log(r"ROM loaded ok", 30, mark) is not None, "the Mac restarts")
    print(f"        waiting {args.boot_seconds} s for the Finder", flush=True)
    time.sleep(args.boot_seconds)
    if not first:
        # The first part ended the app without shutting the Mac down, so the
        # System opens with its notice about that: OK it.
        if capture(): tap("Return"); release()
        time.sleep(40)
    check(desktop_drawn(), "the Finder's desktop is on the screen")
    return app

def stop(app):
    app.terminate()
    try: app.wait(15)
    except subprocess.TimeoutExpired: app.kill()

if os.path.exists(log_path): os.remove(log_path)
print("-- 1: put away in the Mac")
app = start(True)
try:
    check(app.poll() is None, "the app is running")
    shot("finder-with-disk")
    with_disk = icon_patch()
    check(capture(), "a click captures the mouse")
    move_by(-700, -520, 2)                             # into the top left corner
    move_by(ICON[0], ICON[1])
    time.sleep(0.3)
    shot("pointer-on-the-disk")
    button(1, True); time.sleep(0.4)
    move_by(TRASH[0] - ICON[0], TRASH[1] - ICON[1])
    time.sleep(0.6)
    button(1, False)
    time.sleep(2.5)
    shot("the-finder-asks")
    mark = len(log_text())
    tap("Return")                                      # OK, the default button
    asked = time.time()
    put = wait_log(r"\[disk\] the Mac put away " + re.escape(label) + r"; it is off the second SCSI seat", 15, mark)
    took = time.time() - asked
    check(put is not None, "the app takes the disk off the seat when the Mac puts it away")
    if put:
        check(2.0 <= took < 8.0, f"three seconds after the Finder let go of it ({took:.1f} s; 2 to 8)")
    time.sleep(1.5)
    release()
    shot("put-away")
    gone = icon_patch()
    check(with_disk is not None and gone is not None and with_disk != gone,
          "CONTROL: the disk's icon was on the desktop, and is not now")
    menu = open_menu(78)                               # Machine
    check(menu is not None, "the Machine menu opens")
    if menu:
        mark = len(log_text())
        click(menu[1] + 100, menu[2] + 106)            # Reset
        check(wait_log(r"ROM loaded ok", 30, mark) is not None, "the Mac is reset")
        time.sleep(args.boot_seconds)
        if capture(): tap("Return"); release()         # the System's "not shut down properly" notice
        time.sleep(40)
        shot("after-reset")
        check(desktop_drawn(), "the Finder's desktop is on the screen again")
        check(icon_patch() == gone, "after the reset the disk has not come back")
        check("transfer disk built" not in log_text()[mark:], "and nothing rebuilt it")
    check(app.poll() is None, "the app is still running")
finally:
    stop(app)

print("-- 2: File > Remove Dropped Disk")
app = start(False)
try:
    check(app.poll() is None, "the app is running")
    shot("finder-with-disk-again")
    check(icon_patch() == with_disk, "the dropped disk is on the desktop again")
    menu = open_menu(22)                               # File
    check(menu is not None, "the File menu opens")
    if menu:
        shot("file-menu")
        mark = len(log_text())
        click(menu[1] + 100, menu[2] + 520)            # Remove Dropped Disk
        off = wait_log(r"\[disk\] " + re.escape(label) + r" taken off the second SCSI seat", 10, mark)
        check(off is not None, "the menu command takes the disk off the seat")
        time.sleep(8.0)
        shot("removed")
        check(icon_patch() == gone, "and its icon leaves the Mac's desktop")
        menu = open_menu(22)
        if menu:
            shot("file-menu-after")
            mark = len(log_text())
            click(menu[1] + 100, menu[2] + 520)
            time.sleep(1.0)
            check("second SCSI seat" not in log_text()[mark:], "with no dropped disk the menu entry does nothing")
            tap("Escape")
    check(app.poll() is None, "the app is still running at the end")
finally:
    stop(app)

log = log_text()
# Every reset and every start after the first hands the machine its parameter
# RAM back; a machine that never saved any has nothing to hand.
check(os.path.exists(os.path.join(profile, "pram-quadra950.bin")), "the Quadra 950's parameter RAM was saved")
check(len(re.findall(r"parameter RAM restored", log)) >= 3, "and given back to the machine at each restart")
bad = [l for l in log.splitlines() if re.search(r"UNHANDLED|FATAL|frame tick failed|load failed|access fault|illegal instruction|would not let go", l)]
check(not bad, "no errors in the app's log" + (": " + bad[0][:160] if bad else ""))
for line in log.splitlines():
    if re.search(r"\[disk\]|drop", line) and "perf:" not in line:
        print("        " + line[25:185])
print("DROP DISK TEST " + ("PASSED" if not failures else f"FAILED ({len(failures)})"))
sys.exit(1 if failures else 0)
