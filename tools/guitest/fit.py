#!/usr/bin/env python3
"""Checks that the window stays on the display when the Mac's screen changes size.

    tools/headless.sh python3 tools/guitest/fit.py --rom QUADRA650.ROM [--app FILE] [--shots DIR]

On the 1280x1024 virtual screen, with a Quadra 650:
  1. starts at 1x on the 13-inch display        -> the window is exactly the Mac's 640x480 plus its bars
  2. drags the window toward the bottom right, then picks the 21-inch display
     from Machine > Monitor, as a user would    -> the 1152x870 window is moved back onto the screen
  3. starts again at 2x on the 21-inch display  -> 2304x1740 cannot fit: the window is as large as
                                                    the screen allows and the picture keeps its shape

Step 1 is the control for the other two: it shows the window does follow the
Mac's screen when that fits. Needs python-xlib.
"""
import argparse, json, os, re, subprocess, sys, time
from Xlib import X, display
from Xlib.ext import xtest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--rom", required=True)
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
ap.add_argument("--shots", default=None, help="folder for a screenshot of each step")
args = ap.parse_args()
for need in (args.rom, args.app):
    if not os.path.exists(need):
        sys.exit(f"fit test: missing {need}")
config = os.environ.get("XDG_CONFIG_HOME")
if not config or os.path.realpath(config).startswith(os.path.realpath(os.path.expanduser("~/.config"))):
    sys.exit("fit test: refusing to run outside tools/headless.sh (it would use the real profile)")
profile = os.path.join(config, "OpenMac")
os.makedirs(profile, exist_ok=True)
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

def wait_log(pattern, timeout=30.0, start=0):
    end = time.time() + timeout
    while time.time() < end:
        m = re.search(pattern, log_text()[start:])
        if m: return m
        time.sleep(0.1)
    return None

def shot(name):
    if not args.shots: return
    os.makedirs(args.shots, exist_ok=True)
    subprocess.run(["import", "-window", "root", os.path.join(args.shots, name + ".png")], stderr=subprocess.DEVNULL)

d = display.Display()
root = d.screen().root
SCREEN_W, SCREEN_H = d.screen().width_in_pixels, d.screen().height_in_pixels

def windows():
    """The viewable top-level windows: (id, x, y, width, height)."""
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

def start(settings):
    if os.path.exists(log_path): os.remove(log_path)
    with open(os.path.join(profile, "settings.json"), "w") as f:
        json.dump(dict({"Model": "quadra650", "LastRomQuadra": os.path.abspath(args.rom)}, **settings), f)
    app = subprocess.Popen([args.app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = wait_log(r"display: first guest frame shown") is not None
    time.sleep(1.5)   # the window is sized once the first frame has been laid out
    return app, ok

def stop(app):
    app.terminate()
    try: app.wait(10)
    except subprocess.TimeoutExpired: app.kill()
    time.sleep(0.5)

def main_window():
    m = re.search(r"window: platform handle XID 0x([0-9A-Fa-f]+)", log_text())
    wid = int(m.group(1), 16) if m else None
    for w in windows():
        if w[0] == wid: return w
    return None

def on_screen(w):
    return w is not None and w[1] >= 0 and w[2] >= 0 and w[1] + w[3] <= SCREEN_W and w[2] + w[4] <= SCREEN_H

def describe(w):
    return "no window" if w is None else f"{w[3]}x{w[4]} at {w[1]},{w[2]}"

# ---- 1. the control: a Mac screen that fits is shown at its own size ----------------
app, ok = start({"Scale": 1, "MonitorQuadra": "13-inch RGB"})
bars_w = bars_h = None
try:
    check(ok, "the Quadra 650 starts on the 13-inch display")
    w = main_window()
    shot("1-13-inch")
    check(w is not None and w[3] == 640 and 480 < w[4] <= 480 + 120,
          f"at 1x the window is the Mac's 640x480 plus its bars ({describe(w)})")
    check(on_screen(w), "and it is on the screen")
    if w: bars_w, bars_h = w[3] - 640, w[4] - 480

    # ---- 2. the user's path: drag toward the corner, pick a bigger display ----------
    if w:
        win = d.create_resource_object("window", w[0])
        win.configure(x=SCREEN_W - 500, y=SCREEN_H - 400); d.sync(); time.sleep(1.0)
        w = main_window()
        print(f"        dragged to {describe(w)}")
        before = {x[0] for x in windows()}
        mark = len(log_text())
        click(w[1] + 79, w[2] + 16)                      # Machine, in the menu bar
        menus = [x for x in windows() if x[0] not in before]
        check(len(menus) == 1, "the Machine menu opens")
        if menus:
            click(menus[0][1] + 64, menus[0][2] + 44)    # Monitor, its second entry
            subs = [x for x in windows() if x[0] not in before and x[0] != menus[0][0]]
            check(len(subs) == 1, "the Monitor list opens")
            if subs:
                shot("2-monitor-list")
                click(subs[0][1] + 140, subs[0][2] + 17 + 27 * 5)   # the sixth display: 21-inch
                picked = wait_log(r"monitor: 21-inch Color", 10, mark) is not None
                check(picked, "the 21-inch display is picked from the list")
                wait_log(r"Quadra 650 created .*21-inch", 20, mark)
                time.sleep(3.0)
                w = main_window()
                shot("2-21-inch")
                check(w is not None and (w[3], w[4]) == (1152 + bars_w, 870 + bars_h),
                      f"the window takes the new display's 1152x870 ({describe(w)})")
                check(on_screen(w), f"and it was moved back onto the {SCREEN_W}x{SCREEN_H} screen")
finally:
    stop(app)

# ---- 3. a Mac screen that cannot fit ------------------------------------------------
app, ok = start({"Scale": 2, "MonitorQuadra": "21-inch Color"})
try:
    check(ok, "the Quadra 650 starts at 2x on the 21-inch display")
    w = main_window()
    shot("3-21-inch-2x")
    check(on_screen(w), f"the window is on the {SCREEN_W}x{SCREEN_H} screen ({describe(w)})")
    if w and bars_h is not None:
        pw, ph = w[3] - bars_w, w[4] - bars_h
        check(abs(pw / ph - 1152 / 870) < 0.01, f"the picture keeps the Mac screen's shape ({pw}x{ph})")
        check(pw >= 0.9 * min(SCREEN_W, (SCREEN_H - bars_h) * 1152 / 870),
              "and is as large as the screen allows")
finally:
    stop(app)

bad = [l for l in log_text().splitlines() if re.search(r"UNHANDLED|FATAL|frame tick failed", l)]
check(not bad, "no errors in the app's log" + (": " + bad[0][:160] if bad else ""))
print("FIT TEST " + ("PASSED" if not failures else f"FAILED ({len(failures)})"))
sys.exit(1 if failures else 0)
