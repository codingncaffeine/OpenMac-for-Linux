#!/usr/bin/env python3
"""A file dropped on the window rides in on its own disk; this checks both ways of
getting rid of that disk for good, and that the Mac's own restart keeps it.

    tools/headless.sh python3 tools/guitest/dropdisk.py --rom ROM --hard-disk SYSTEM.img
        (--file BIG-FILE | --state DESK.state) [--model classic|iifx|quadra650|quadra950|se30]
        [--video-rom FILE] [--ram MB] [--icon X,Y] [--trash X,Y] [--restart X,Y,DOWN]
        [--boot-seconds N] [--app FILE] [--shots DIR]

SYSTEM.img is a startup disk (a copy is used); BIG-FILE is any file over 1.3 MB,
which is what becomes a disk on the second SCSI seat. --model is the machine
(default: the Quadra 950 with Mac OS 8). --icon and --trash are where the
dropped disk's icon and the Trash sit on the Mac's screen (defaults: second
place in the right-hand column and the bottom right of a 640x480 desktop).
--video-rom is the SE/30's real video ROM file (without it: OpenMac's own).
--restart is where the Finder's Special menu is in the Mac's menu bar and how
far below it Restart is; with it the test also has the Mac restart itself.

With --state the Mac starts at its desktop from a saved state instead of from
power-on, with the disk already mounted: about three and a half minutes
instead of nine. Such a state is made headless, with 32 MB as the test uses:

    mkdir drop && cp BIG-FILE drop/
    build/tests/openmac_trace950 --rom Q950.ROM --banks 16 16 0 0 --harddisk SYSTEM.img \
        --dropbox drop --frames 7000 --save-state DESK.state

(7000 frames is past the Finder's start on Mac OS 8.1; --shot F.ppm shows where
it ended.) The state carries both disks, so SYSTEM.img only has to be there.
For the SE/30, with the 8 MB and OpenMac's own video ROM the test then runs with
(--ram 8, no --video-rom):

    build/tests/openmac_tracese30 --rom SE30.ROM --ram 8 --harddisk SYSTEM.img \
        --dropbox drop --frames 4200 --save-state DESK.state

  1. The Mac starts with the dropped disk on its desktop. Its icon is dragged to
     the Trash and the Finder's question is answered OK -> the app takes the disk
     off the seat, and after a reset it does not come back.
  2. The app starts again with the same file. With --restart the Mac is restarted
     from its own Special menu first -> the new startup mounts the disk again
     and its icon is back on the desktop. Then File > Remove Dropped Disk takes
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
ap.add_argument("--file")
ap.add_argument("--state")
ap.add_argument("--model", default="quadra950", choices=["classic", "iifx", "quadra650", "quadra950", "se30"])
ap.add_argument("--video-rom", help="the SE/30's video ROM file")
ap.add_argument("--ram", type=int, default=None, help="megabytes (default: 4 on the Classic, 32 elsewhere)")
ap.add_argument("--icon", default="591,115")
ap.add_argument("--trash", default="587,426")
ap.add_argument("--restart", default=None, help="X,Y,DOWN: the Special menu's place and Restart's distance below it")
ap.add_argument("--boot-seconds", type=int, default=150, help="longest wait for a start to reach a still screen")
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
ap.add_argument("--shots", default=None, help="folder for a screenshot of each step")
args = ap.parse_args()
if bool(args.file) == bool(args.state):
    sys.exit("drop disk test: give --file or --state, one of them")
for need in (args.rom, args.hard_disk, args.file or args.state, args.app) + ((args.video_rom,) if args.video_rom else ()):
    if not os.path.exists(need):
        sys.exit(f"drop disk test: missing {need}")
if args.file and os.path.getsize(args.file) <= 1_300_000:
    sys.exit("drop disk test: --file must be over 1.3 MB (a smaller one rides on a floppy)")
config = os.environ.get("XDG_CONFIG_HOME")
if not config or os.path.realpath(config).startswith(os.path.realpath(os.path.expanduser("~/.config"))):
    sys.exit("drop disk test: refusing to run outside tools/headless.sh (it would use the real profile)")
ICON = tuple(int(v) for v in args.icon.split(","))
TRASH = tuple(int(v) for v in args.trash.split(","))
RESTART = tuple(int(v) for v in args.restart.split(",")) if args.restart else None
# Per machine: the settings' suffix, the parameter RAM file's name, the Mac's
# screen, the core's line when a startup has mounted the second disk, and how
# far down the Machine menu Reset is (the entries above it differ: the IIfx
# has its card's ROM there, the Quadra 950 its video RAM, the SE/30 its two
# video ROM entries in the Monitor menu's place).
SUFFIX, PRAM, SCREEN, MOUNTED, RESET_ROW = {
    "classic":   ("",          "classic",   (512, 342), r"hd2: mount result 0000", 80),
    "iifx":      ("Iifx",      "iifx",      (640, 480), r"IIfx second disk drive 5 mount result=0", 106),
    "quadra650": ("Quadra",    "quadra",    (640, 480), r"hd: drive 9 mount result 0", 80),
    "quadra950": ("Quadra950", "quadra950", (640, 480), r"hd: drive 9 mount result 0", 106),
    "se30":      ("Se30",      "se30",      (512, 342), r"hd: drive 9 mount result 0", 106),
}[args.model]
RAM = args.ram or (4 if args.model == "classic" else 32)
profile = os.path.join(config, "OpenMac")
os.makedirs(profile, exist_ok=True)
log_path = os.path.join(profile, "openmac.log")
disk = os.path.join(profile, "startup.img")
shutil.copyfile(args.hard_disk, disk)
label = os.path.basename(args.file) if args.file else None     # with a state: read from the log
settings = {"Model": args.model, "Scale": 1, "LastRom" + SUFFIX: os.path.abspath(args.rom),
            "LastHardDisk" + SUFFIX: disk, "RamMB" + SUFFIX: RAM, "ExternalDrive": False}
if args.video_rom: settings["VideoRomSe30"] = os.path.abspath(args.video_rom)
with open(os.path.join(profile, "settings.json"), "w") as f:
    json.dump(settings, f)

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
    pointer by what the mouse moved, with none of its own speeding up: one
    count every 40 ms, over two frames. At one every 20 ms two counts can fall
    between the same two polls of the mouse; the Mac then speeds the pointer
    up, and it ends 10 to 20 dots past its target. (Bigger steps are for
    running into a corner, where speeding up does no harm.)"""
    n = max(abs(dx), abs(dy)) // step or 1
    sx = sy = 0
    for i in range(1, n + 1):
        tx, ty = dx * i // n, dy * i // n
        xtest.fake_input(d, X.MotionNotify, detail=1, x=tx - sx, y=ty - sy); d.sync()
        sx, sy = tx, ty
        time.sleep(0.04 if step == 1 else 0.02)

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
    out = subprocess.run(["import", "-window", "root", "-crop",
                          f"{SCREEN[0]}x{SCREEN[1]}+{w[1]}+{w[2] + MENU_BAR}", "+repage",
                          "-format", "%k", "info:"], capture_output=True, text=True).stdout.strip()
    # A black-and-white screen has two colors however much is on it.
    return out.isdigit() and int(out) > (200 if args.model.startswith("quadra") else 1)

def screen_hash():
    w = main_window()
    raw = subprocess.run(["import", "-window", "root", "-crop",
                          f"{SCREEN[0]}x{SCREEN[1] - 20}+{w[1]}+{w[2] + MENU_BAR + 20}", "+repage",
                          "rgb:-"], capture_output=True).stdout
    return hashlib.sha256(raw).hexdigest() if raw else None

def wait_still(longest):
    """Wait until the Mac shows a picture that has not changed for ten seconds
    (its menu bar's clock aside): the Finder's desktop, or a notice waiting for
    an answer. False when that takes longer than `longest` seconds."""
    end = time.time() + longest
    last, since = None, time.time()
    while time.time() < end:
        now = screen_hash() if desktop_drawn() else None
        if now is None or now != last:
            last, since = now, time.time()
        elif time.time() - since >= 10.0:
            return True
        time.sleep(2.0)
    return False

def wait_until(condition, longest):
    end = time.time() + longest
    while time.time() < end:
        if condition(): return True
        time.sleep(1.0)
    return False

def settle(what):
    """A start is over when the screen is still. The System opens with a notice
    when the Mac was not shut down; Return answers it, and does nothing else."""
    ok = wait_still(args.boot_seconds)
    if ok and capture():
        tap("Return"); release()
        ok = wait_still(60)
    check(ok and desktop_drawn(), what)

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
    click(w[1] + SCREEN[0] // 2, w[2] + MENU_BAR + SCREEN[1] - 40)   # the capturing click is not a Mac click
    return wait_log(r"input: capture engaged", 5, mark) is not None
def release():
    button(2, True); button(2, False); time.sleep(0.5)

def start():
    """Start the app with the dropped disk in the Mac: from the saved state, or
    with the file on its command line (the same road as a drop) and a Yes to the
    restart that loads the seat's driver."""
    global label
    mark = len(log_text())
    if args.state:
        app = subprocess.Popen([args.app], env=dict(os.environ, OPENMAC_STATE=os.path.abspath(args.state)),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        loaded = wait_log(r"\[state\] loaded [^\n]*, with “([^”\n]+)” on the second SCSI seat", 60, mark)
        check(loaded is not None, "the Mac starts from the saved state with a disk on the second seat")
        if loaded: label = loaded.group(1)
        else: label = label or "?"
    else:
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
    settle("the Finder's desktop is on the screen")
    return app

def reset_settle_seconds(text):
    """Seconds from a ROM load being asked for to the old machine's volumes
    being flushed: the flush runs on the guest, at its next event call."""
    stamp = r"^\S+ (\d+):(\d+):(\d+\.\d+)  "
    a = re.search(stamp + r"load ROM:", text, re.M)
    b = re.search(stamp + r"(?:hard disk: (?:volumes flushed|nothing to (?:settle|flush))|IIfx hard disk: guest cache flushed)", text, re.M)
    if not a or not b: return None
    seconds = lambda m: int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return seconds(b) - seconds(a)

def stop(app):
    app.terminate()
    try: app.wait(15)
    except subprocess.TimeoutExpired: app.kill()

if os.path.exists(log_path): os.remove(log_path)
print("-- 1: put away in the Mac")
app = start()
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
        check(1.5 <= took < 8.0, f"seconds after the Finder let go of it, not at once ({took:.1f} s; 1.5 to 8)")
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
        click(menu[1] + 100, menu[2] + RESET_ROW)      # Reset
        reset = wait_log(r"load ROM: [^\n]*\(RAM=(\d+) MB[^\n]*\n(?:[^\n]*\n)*?[^\n]*ROM loaded ok", 30, mark)
        check(reset is not None and int(reset.group(1)) == RAM,
              "the Mac is reset, with the memory it had"
              + (f" ({reset.group(1)} MB; {RAM} before)" if reset else ""))
        took = reset_settle_seconds(log_text()[mark:])
        check(took is not None and took < 3.0,
              "the reset flushed the Mac's volumes without a stall"
              + (f" ({took:.1f} s; under 3)" if took is not None else " (no flush line in the log)"))
        settle("the Finder's desktop is on the screen again")
        shot("after-reset")
        # A Finder that keeps no place for the Trash puts it under the last
        # disk at every start, which is where the dropped disk was: then the
        # picture is not the "gone" one, and the log has to say the disk was
        # not mounted again.
        after = icon_patch()
        moved = after != gone and after != with_disk and re.search(MOUNTED, log_text()[mark:]) is None
        check(after == gone or moved, "after the reset the disk has not come back"
              + (" (its place holds something else now; the startup did not mount it)" if moved else ""))
        check("transfer disk built" not in log_text()[mark:] and "[state] loaded" not in log_text()[mark:],
              "and nothing put it back")
    check(app.poll() is None, "the app is still running")
finally:
    stop(app)

print("-- 2: File > Remove Dropped Disk")
app = start()
try:
    check(app.poll() is None, "the app is running")
    shot("finder-with-disk-again")
    check(icon_patch() == with_disk, "the dropped disk is on the desktop again")
    if RESTART:
        check(capture(), "a click captures the mouse")
        move_by(-700, -520, 2)                         # into the top left corner
        move_by(RESTART[0], RESTART[1])
        time.sleep(0.3)
        mark = len(log_text())
        button(1, True); time.sleep(0.5)
        move_by(0, RESTART[2]); time.sleep(0.5)
        shot("special-menu")
        button(1, False)
        again = wait_log(MOUNTED, 240, mark)
        check(again is not None, "the Mac restarts itself, and its new startup mounts the dropped disk")
        release()
        # The mount line is the new startup's; the icon follows when its
        # Finder has drawn the desktop.
        back = wait_until(lambda: icon_patch() == with_disk, 240)
        shot("after-the-macs-restart")
        check(back, "the dropped disk is on the desktop again after it")
        check("put away" not in log_text()[mark:], "and the restart was not taken for a put-away")
        check(app.poll() is None, "the app is running")
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
check(os.path.exists(os.path.join(profile, f"pram-{PRAM}.bin")), "the machine's parameter RAM was saved")
check(len(re.findall(r"parameter RAM restored", log)) >= (1 if args.state else 3),
      "and given back to the machine at a restart")
bad = [l for l in log.splitlines() if re.search(r"UNHANDLED|FATAL|frame tick failed|load failed|access fault|illegal instruction|would not let go|did not return", l)]
check(not bad, "no errors in the app's log" + (": " + bad[0][:160] if bad else ""))
for line in log.splitlines():
    if re.search(r"\[disk\]|drop", line) and "perf:" not in line:
        print("        " + line[25:185])
print("DROP DISK TEST " + ("PASSED" if not failures else f"FAILED ({len(failures)})"))
sys.exit(1 if failures else 0)
