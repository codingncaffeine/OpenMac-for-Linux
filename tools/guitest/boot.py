#!/usr/bin/env python3
"""Boots one machine in the real window and reports what the log and the screen say.

    tools/headless.sh python3 tools/guitest/boot.py --model classic|iifx|quadra650 --rom FILE
        [--floppy FILE] [--hard-disk FILE] [--video-rom FILE] [--ram MB] [--seconds N]
        [--shot OUT.png] [--burst FROM:TO:PREFIX] [--speed-band LO:HI] [--app FILE]

The floppy and the hard disk are copied to the scratch profile first, so the
originals are never written. --burst saves a screenshot about four times a
second between FROM and TO seconds after the start, as PREFIX-NN.png. Passes when the window shows guest frames for the whole run, the machine
keeps to the speed band, sound is fed without underruns (on the machines that
report it), and the log holds no error.
"""
import argparse, json, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=["classic", "iifx", "quadra650"])
ap.add_argument("--rom", required=True)
ap.add_argument("--floppy")
ap.add_argument("--hard-disk")
ap.add_argument("--burst")
ap.add_argument("--set", action="append", default=[], metavar="KEY=JSON",
                help="one more settings.json field, e.g. --set DropBox=true")
ap.add_argument("--video-rom")
ap.add_argument("--ram", type=int)
ap.add_argument("--seconds", type=int, default=30)
ap.add_argument("--shot")
ap.add_argument("--speed-band", default="95:105", help="lowest:highest steady speed, percent")
ap.add_argument("--app", default=os.path.join(ROOT, "bin", "openmac"))
a = ap.parse_args()

config = os.environ.get("XDG_CONFIG_HOME")
if not config or os.path.realpath(config).startswith(os.path.realpath(os.path.expanduser("~/.config"))):
    sys.exit("boot test: refusing to run outside tools/headless.sh (it would use the real profile)")
profile = os.path.join(config, "OpenMac")
os.makedirs(profile, exist_ok=True)
floppy = None
if a.floppy:
    floppy = os.path.join(profile, os.path.basename(a.floppy))
    shutil.copyfile(a.floppy, floppy)
hard_disk = None
if a.hard_disk:
    hard_disk = os.path.join(profile, os.path.basename(a.hard_disk))
    shutil.copyfile(a.hard_disk, hard_disk)
suffix = {"classic": "", "iifx": "Iifx", "quadra650": "Quadra"}[a.model]
settings = {"Model": a.model, "Scale": 1, "LastRom" + suffix: os.path.abspath(a.rom),
            "LastFloppy" + suffix: floppy, "LastHardDisk" + suffix: hard_disk, "ExternalDrive": False}
for item in a.set:
    key, value = item.split("=", 1)
    settings[key] = json.loads(value)
if a.video_rom: settings["VideoRomIifx"] = os.path.abspath(a.video_rom)
if a.ram: settings["RamMB" + suffix] = a.ram
with open(os.path.join(profile, "settings.json"), "w") as f:
    json.dump(settings, f)
log_path = os.path.join(profile, "openmac.log")

err_path = os.path.join(profile, "stderr.txt")
started = time.time()
app = subprocess.Popen([a.app], stdout=subprocess.DEVNULL, stderr=open(err_path, "w"))
alive, died = True, ""
try:
    end = started + a.seconds
    burst_from = burst_to = None
    if a.burst:
        f, t, burst_prefix = a.burst.split(":", 2)
        burst_from, burst_to, burst_n = started + float(f), started + float(t), 0
        os.makedirs(os.path.dirname(os.path.abspath(burst_prefix)), exist_ok=True)
    while time.time() < end:
        if app.poll() is not None:
            alive = False
            died = f": it exited with code {app.returncode} after {time.time() - started:.0f} s"
            break
        if burst_from is not None and burst_from <= time.time() <= burst_to:
            subprocess.run(["import", "-window", "root", f"{burst_prefix}-{burst_n:02d}.png"], stderr=subprocess.DEVNULL)
            burst_n += 1
            time.sleep(0.1)
            continue
        time.sleep(0.25)
    if a.shot and alive:
        os.makedirs(os.path.dirname(os.path.abspath(a.shot)), exist_ok=True)
        subprocess.run(["import", "-window", "root", a.shot], stderr=subprocess.DEVNULL)
finally:
    app.terminate()
    try: app.wait(10)
    except subprocess.TimeoutExpired: app.kill()

log = open(log_path, errors="replace").read() if os.path.exists(log_path) else ""
failures = []
def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok: failures.append(what)

check(alive, f"the app ran for {a.seconds} s" + died)
if not alive:
    for line in open(err_path, errors="replace").read().splitlines()[-25:]: print("        | " + line[:200])
    for line in log.splitlines()[-6:]: print("        log| " + line[:200])
m = re.search(r"backend: native core \(libopenmac_c\.so\), (.+)", log)
check(m is not None, "the native core loaded" + (f" ({m.group(1)})" if m else ""))
check("ROM loaded ok" in log, "the ROM loaded")
m = re.search(r"display: first guest frame shown \((\d+)x(\d+)\)", log)
check(m is not None, "guest frames reach the window" + (f" ({m.group(1)}x{m.group(2)})" if m else ""))
perf = [(float(f), int(u)) for f, u in re.findall(r"perf: fps=([\d.]+) .*underruns=(\d+)", log)]
steady = perf[3:]   # the first seconds include start-up
if steady:
    slow = [f for f, _ in steady if not 57.0 <= f <= 63.0]
    check(len(slow) <= len(steady) // 10, f"about 60 frames a second ({min(f for f, _ in steady):.1f}"
          f" to {max(f for f, _ in steady):.1f} over {len(steady)} s, {len(slow)} outside 57-63)")
    check(sum(u for _, u in steady) == 0, f"no sound underruns ({sum(u for _, u in steady)})")
else:
    print("        (this machine does not report frame rate or sound queue lines)")
lo, hi = (float(x) for x in a.speed_band.split(":"))
speeds = [float(x) for x in re.findall(r"  speed: (\d+)%", log)][1:]   # the first covers start-up
if speeds:
    out = [x for x in speeds if not lo <= x <= hi]
    check(not out, f"speed stays in {lo:.0f}-{hi:.0f}% ({min(speeds):.0f} to {max(speeds):.0f}% over "
          f"{len(speeds)} readings, {len(out)} outside)")
else:
    check(False, "no speed lines in the log")
bad = [l for l in log.splitlines() if re.search(r"UNHANDLED|FATAL|frame tick failed|load failed|could not", l)]
check(not bad, "no errors in the app's log" + (": " + bad[0][:160] if bad else ""))
for line in log.splitlines():
    if re.search(r"video|8•24|monitor|GC ROM|EXC vec=3|\[disk\]|SuperDrive|SCSI disk|mounted|drop box|folder disk", line) and "[core] boot f=" not in line:
        print("        " + line[25:185])
print("BOOT TEST " + ("PASSED" if not failures else f"FAILED ({len(failures)})"))
sys.exit(1 if failures else 0)
