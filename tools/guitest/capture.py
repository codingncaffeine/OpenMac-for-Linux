#!/usr/bin/env python3
"""Drives the real window through captured input and checks what reaches the Mac.

Run through the headless wall, with a Macintosh Classic ROM of your own:

    tools/headless.sh python3 tools/guitest/capture.py [--rom FILE] [--app FILE] [--shots DIR]

It starts the app on a scratch profile, then, with synthetic X input (XTEST):
  1. presses a key on the bare window          -> the Mac gets it through the toolkit
  2. presses a desktop shortcut it has claimed -> the "desktop" (this script) gets it, the Mac does not
  3. clicks the Mac's screen                   -> input is captured
  4. presses the same shortcut                 -> the Mac gets it, the desktop does not
  5. moves and clicks                          -> the Mac gets raw motion and the button
  6. middle-clicks                             -> capture ends; the shortcut is the desktop's again

Step 2 is the control for step 4: it shows the shortcut really is taken by
someone else while input is not captured. Needs python-xlib.
"""
import argparse, json, os, re, subprocess, sys, time
from Xlib import X, XK, display
from Xlib.ext import xtest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--rom", default=os.path.join(ROOT, "gitignore", "1990-10 - A49F9914 - Mac Classic.rom"))
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
ap.add_argument("--shots", default=None, help="folder for screenshots of each stage")
args = ap.parse_args()

for need in (args.rom, args.app):
    if not os.path.exists(need):
        sys.exit(f"capture test: missing {need}")
config = os.environ.get("XDG_CONFIG_HOME")
if not config or os.path.realpath(config).startswith(os.path.realpath(os.path.expanduser("~/.config"))):
    sys.exit("capture test: refusing to run outside tools/headless.sh (it would use the real profile)")

profile = os.path.join(config, "OpenMac")
os.makedirs(profile, exist_ok=True)
with open(os.path.join(profile, "settings.json"), "w") as f:
    json.dump({"Model": "classic", "RamMB": 4, "Scale": 2, "LastRom": args.rom}, f)
log_path = os.path.join(profile, "openmac.log")

failures = []
def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok: failures.append(what)

def log_text():
    try:
        with open(log_path, errors="replace") as f: return f.read()
    except FileNotFoundError:
        return ""

def wait_log(pattern, timeout=15.0, start=0):
    end = time.time() + timeout
    while time.time() < end:
        m = re.search(pattern, log_text()[start:])
        if m: return m
        time.sleep(0.1)
    return None

def shot(name):
    if not args.shots: return
    os.makedirs(args.shots, exist_ok=True)
    subprocess.run(["import", "-window", "root", os.path.join(args.shots, name + ".png")],
                   stderr=subprocess.DEVNULL)

d = display.Display()
root = d.screen().root
app = subprocess.Popen([args.app], env=dict(os.environ, OPENMAC_INPUT_TRACE="1"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    check(wait_log(r"display: first guest frame shown", 30) is not None, "the Mac's screen is being drawn")
    m = wait_log(r"input: X11 capture ready .*window 0x([0-9A-F]+)\)", 5)
    check(m is not None, "the X11 capture is available")
    if not m: raise SystemExit
    win = d.create_resource_object("window", int(m.group(1), 16))
    geo = win.get_geometry()
    pos = win.translate_coords(root, 0, 0)
    wx, wy = -pos.x, -pos.y
    cx, cy = wx + geo.width // 2, wy + geo.height // 2
    print(f"  window 0x{win.id:X} at {wx},{wy} size {geo.width}x{geo.height}")
    time.sleep(1.0)

    def key(code, down):
        xtest.fake_input(d, X.KeyPress if down else X.KeyRelease, code); d.sync(); time.sleep(0.06)
    def tap(code):
        key(code, True); key(code, False)
    def button(n, down):
        xtest.fake_input(d, X.ButtonPress if down else X.ButtonRelease, n); d.sync(); time.sleep(0.08)
    def move_to(x, y):
        xtest.fake_input(d, X.MotionNotify, x=x, y=y); d.sync(); time.sleep(0.05)
    def move_by(dx, dy):
        xtest.fake_input(d, X.MotionNotify, detail=1, x=dx, y=dy); d.sync(); time.sleep(0.02)

    kq = d.keysym_to_keycode(XK.XK_q)
    kf9 = d.keysym_to_keycode(XK.XK_F9)
    check(kq == 24 and kf9 == 75, f"the X server uses kernel key codes (q={kq}, F9={kf9})")

    # There is no window manager here, so nothing has given the window focus.
    win.set_input_focus(X.RevertToParent, X.CurrentTime); d.sync(); time.sleep(0.3)

    # This script plays the desktop: it claims F9 the way a window manager
    # claims a global shortcut, with a passive grab on the root window.
    for mods in (0, X.Mod2Mask, X.LockMask, X.Mod2Mask | X.LockMask):
        root.grab_key(kf9, mods, True, X.GrabModeAsync, X.GrabModeAsync)
    d.sync()
    def desktop_presses():
        n = 0
        while d.pending_events():
            e = d.next_event()
            if e.type == X.KeyPress and e.detail == kf9: n += 1
        return n

    print("-- not captured")
    mark = len(log_text())
    tap(kq)
    check(wait_log(r"input trace: key \$0C down", 3, mark) is not None, "a plain key reaches the Mac (Q = ADB $0C)")
    mark = len(log_text())
    tap(kf9); time.sleep(0.3)
    check(desktop_presses() == 1, "CONTROL: the desktop's shortcut (F9) goes to the desktop")
    check(wait_log(r"input trace: key \$65 down", 0.5, mark) is None, "CONTROL: and the Mac does not get it")
    shot("1-not-captured")

    print("-- captured")
    mark = len(log_text())
    move_to(cx, cy)
    button(1, True); button(1, False)
    check(wait_log(r"input: capture engaged", 5, mark) is not None, "a click on the screen captures the mouse and keyboard")
    check(wait_log(r"input trace: button", 0.5, mark) is None, "the capturing click is not a Mac click")
    time.sleep(0.3); desktop_presses()
    mark = len(log_text())
    tap(kf9); time.sleep(0.3)
    check(wait_log(r"input trace: key \$65 down", 2, mark) is not None, "the desktop's shortcut now reaches the Mac (F9 = ADB $65)")
    check(desktop_presses() == 0, "and the desktop no longer gets it")
    mark = len(log_text())
    kmeta = d.keysym_to_keycode(XK.XK_Super_L)
    key(kmeta, True); tap(kq); key(kmeta, False)
    text = ""
    wait_log(r"input trace: key \$37 up", 2, mark)
    text = log_text()[mark:]
    order = re.findall(r"input trace: key \$(37|0C) (down|up)", text)
    check(order == [("37", "down"), ("0C", "down"), ("0C", "up"), ("37", "up")],
          f"Meta+Q arrives as Command-Q, in order ({order})")
    mark = len(log_text())
    key(kq, True); time.sleep(1.5); key(kq, False)   # long enough for the server to auto-repeat it
    wait_log(r"input trace: key \$0C up", 2, mark)
    held_downs = len(re.findall(r"input trace: key \$0C down", log_text()[mark:]))
    mark = len(log_text())
    for _ in range(40): move_by(3, 2)
    button(1, True); button(1, False)
    check(wait_log(r"input trace: button down", 2, mark) is not None and
          wait_log(r"input trace: button up", 2, mark) is not None, "a click while captured is a Mac click")
    ptr = root.query_pointer()
    check(wx <= ptr.root_x < wx + geo.width and wy <= ptr.root_y < wy + geo.height,
          f"the pointer is still inside the window ({ptr.root_x},{ptr.root_y})")
    shot("2-captured")

    print("-- released")
    mark = len(log_text())
    button(2, True); button(2, False)
    m = wait_log(r"input: capture released packets=(\d+) delta=(-?\d+)/(-?\d+) source=xi2-raw raw=(\d+) buttons=(\d+) keys=(\d+)", 5, mark)
    check(m is not None, "a middle click releases the capture")
    if m:
        packets, dx, dy, raw = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        check(raw >= 40, f"raw motion was read from the device ({raw} packets)")
        # 8 key events were typed above; anything beyond is the server repeating the held key.
        repeats = int(m.group(6)) - 8
        check(repeats >= 5, f"CONTROL: the held key was auto-repeated by the server ({repeats} repeats reached the capture)")
        check(held_downs == 1, f"and the Mac saw one press, not {held_downs}")
        check(dx == 120 and dy == 80, f"the Mac was moved by exactly what the mouse moved (120/80, got {dx}/{dy})")
    time.sleep(0.3); desktop_presses()
    mark = len(log_text())
    tap(kf9); time.sleep(0.3)
    check(desktop_presses() == 1, "the desktop's shortcut is the desktop's again")
    check(wait_log(r"input trace: key \$65 down", 0.5, mark) is None, "and the Mac no longer gets it")
    mark = len(log_text())
    tap(kq)
    check(wait_log(r"input trace: key \$0C down", 3, mark) is not None, "plain keys still reach the Mac after the release")
    shot("3-released")
finally:
    app.terminate()
    try: app.wait(10)
    except subprocess.TimeoutExpired: app.kill()

bad = [l for l in log_text().splitlines() if re.search(r"UNHANDLED|FATAL|frame tick failed|capture thread failed", l)]
check(not bad, "no errors in the app's log" + (": " + bad[0] if bad else ""))
print("\nCAPTURE TEST " + ("PASSED" if not failures else f"FAILED ({len(failures)})"))
sys.exit(1 if failures else 0)
