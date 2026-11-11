#!/usr/bin/env bash
# Smoke-tests a built OpenMac artifact: unpacks it, checks what is inside, then
# LAUNCHES it and requires it to stay up, load its own emulator core and its
# bundled SDL3, and write only to a scratch profile. A package can build and
# install cleanly and still not start; only running it shows that.
#
#   tools/headless.sh packaging/smoke-test.sh <artifact> [...]
#     <artifact>: a release .tar.gz, a .deb, or an Arch .pkg.tar.zst
#
# Run it through tools/headless.sh: that supplies the virtual display, the
# private session bus and the wall that makes sound impossible. The launch is
# refused when a sound device is reachable.
# Exit: 0 all passed | 1 a check failed | 2 the launch could not be run
set -uo pipefail

MIN_ASSEMBLIES=150
LAUNCH_SECONDS=15

fail() { printf '  FAIL  %s\n' "$*"; FAILED=1; }
ok()   { printf '  ok    %s\n' "$*"; }

smoke_one() {
    local artifact="$1" tmp payload
    FAILED=0
    printf '\n== %s ==\n' "$(basename "$artifact")"
    [[ -f $artifact ]] || { fail "no such file"; return 1; }
    tmp=$(mktemp -d) || return 1
    trap 'rm -rf "$tmp"; trap - RETURN' RETURN

    case $artifact in
        *.tar.gz|*.tgz|*.pkg.tar.zst|*.pkg.tar.xz) tar -xf "$artifact" -C "$tmp" 2>/dev/null ;;
        *.deb)
            if command -v dpkg-deb >/dev/null; then dpkg-deb -x "$artifact" "$tmp"
            else bsdtar -xOf "$artifact" 'data.tar.*' | bsdtar -xf - -C "$tmp"; fi ;;
        *)  fail "unrecognized artifact type"; return 1 ;;
    esac
    [[ $? -eq 0 ]] || { fail "could not unpack"; return 1; }

    payload=$(find "$tmp" -name OpenMac -type f -perm -u+x -printf '%h\n' 2>/dev/null | head -1)
    [[ -n $payload ]] || { fail "no OpenMac executable in the artifact"; return 1; }
    ok "payload at ${payload#"$tmp"}/"

    local n f
    n=$(find "$payload" -maxdepth 1 -name '*.dll' | wc -l)
    if (( n < MIN_ASSEMBLIES )); then fail "only $n managed assemblies (expected at least $MIN_ASSEMBLIES)"
    else ok "$n managed assemblies"; fi
    for f in OpenMac.dll OpenMac.runtimeconfig.json OpenMac.deps.json System.Private.CoreLib.dll \
             Avalonia.Base.dll libcoreclr.so libhostfxr.so libhostpolicy.so libSkiaSharp.so \
             libHarfBuzzSharp.so libopenmac_c.so; do
        [[ -f "$payload/$f" ]] && ok "$f" || fail "$f is missing"
    done
    # The tarballs and the .deb carry SDL3; an Arch package uses the system's.
    local bundled_sdl=1
    case $artifact in *.pkg.tar.*) bundled_sdl=0 ;; esac
    if (( bundled_sdl )); then
        [[ -f "$payload/libSDL3.so.0" ]] && ok "libSDL3.so.0 (bundled)" || fail "libSDL3.so.0 is missing"
    fi
    if [[ $artifact == *.deb ]]; then
        for f in usr/bin/openmac usr/share/applications/io.github.codingncaffeine.OpenMac.desktop \
                 usr/share/icons/hicolor/256x256/apps/openmac.png \
                 usr/share/metainfo/io.github.codingncaffeine.OpenMac.metainfo.xml; do
            [[ -e "$tmp/$f" ]] && ok "/$f" || fail "/$f is missing"
        done
    fi

    # ---- launch -----------------------------------------------------------------
    if [[ -z ${DISPLAY:-} ]]; then
        printf '  SKIPPED  launch: no DISPLAY. Run through tools/headless.sh.\n'
        return 2
    fi
    if [[ -n "$(ls -A /dev/snd 2>/dev/null)" ]]; then
        printf '  SKIPPED  launch: a sound device is reachable. Run through tools/headless.sh.\n'
        return 2
    fi
    # OpenMac keeps settings and its log under $XDG_CONFIG_HOME/OpenMac. Every XDG
    # folder points into the scratch tree, and the real profile is checked afterwards.
    local xdg=$tmp/xdg real=$HOME/.config/OpenMac before=""
    mkdir -p "$xdg/config" "$xdg/data" "$xdg/cache" "$xdg/state"
    [[ -e $real ]] && before=$(find "$real" -type f -printf '%p %T@\n' 2>/dev/null | sort | md5sum)

    local out=$tmp/launch.out rc start elapsed
    start=$SECONDS
    ( cd "$payload" &&
      exec env XDG_CONFIG_HOME="$xdg/config" XDG_DATA_HOME="$xdg/data" \
               XDG_CACHE_HOME="$xdg/cache" XDG_STATE_HOME="$xdg/state" \
               timeout -k 5 "$LAUNCH_SECONDS" ./OpenMac ) > "$out" 2>&1
    rc=$?
    elapsed=$((SECONDS - start))
    # timeout exits 124 when it had to stop the app (137 if TERM was ignored): the app was still up.
    if (( rc == 124 || rc == 137 )) && (( elapsed >= LAUNCH_SECONDS )); then
        ok "still running after ${LAUNCH_SECONDS} s"
    else
        fail "exited after ${elapsed} s (code $rc)"
        sed 's/^/           | /' "$out" | head -20
    fi
    if grep -qiE 'does not exist|A fatal error|Failed to load|FileNotFoundException|XamlLoadException|DllNotFoundException' "$out"; then
        fail "host or runtime error in the output:"
        grep -iE 'does not exist|A fatal error|Failed to load|FileNotFoundException|XamlLoadException|DllNotFoundException' "$out" |
            sed 's/^/           | /' | head -5
    fi

    local log=$xdg/config/OpenMac/openmac.log line
    if [[ -f $log ]]; then ok "started against the scratch profile"
    else fail "no log under the scratch profile (startup never got that far)"; return 1; fi
    line=$(grep -o 'app startup: .*' "$log" | head -1)
    [[ -n $line ]] && ok "$line" || fail "no version line in the log"
    line=$(grep -o 'backend: .*' "$log" | head -1)
    if [[ $line == "backend: native core (libopenmac_c.so)"* ]]; then ok "$line"
    else fail "the emulator core did not load: ${line:-no backend line}"; fi
    line=$(grep -o 'SDL3: .*' "$log" | head -1)
    if [[ $line != *"(audio import ok)"* ]]; then
        fail "SDL3 did not load: ${line:-no SDL3 line}"
    elif (( bundled_sdl )) && [[ $line != "SDL3: loaded $payload/libSDL3.so.0 "* ]]; then
        fail "SDL3 loaded, but not the bundled copy: $line"
    else
        ok "${line/"$payload"\//<payload>/}"
    fi
    grep -q 'GUI ready' "$log" && ok "the main window came up" || fail "no 'GUI ready' line in the log"
    if grep -qE 'UNHANDLED|FATAL' "$log"; then
        fail "the app logged an error:"; grep -E 'UNHANDLED|FATAL' "$log" | sed 's/^/           | /' | head -5
    fi
    if [[ -e $real ]]; then
        [[ $before == "$(find "$real" -type f -printf '%p %T@\n' 2>/dev/null | sort | md5sum)" ]] ||
            fail "the launch touched the REAL profile $real"
    elif [[ -z $before && -e $real ]]; then
        fail "the launch created the REAL profile $real"
    fi
    return $FAILED
}

(( $# )) || { echo "usage: $(basename "$0") <artifact> [...]" >&2; exit 2; }
rc=0
for a in "$@"; do
    smoke_one "$a"
    case $? in 0) ;; 2) (( rc == 0 )) && rc=2 ;; *) rc=1 ;; esac
done
printf '\n'
case $rc in
    0) echo "SMOKE TEST PASSED: every artifact launches." ;;
    2) echo "SMOKE TEST INCOMPLETE: contents checked, the app was never launched." ;;
    *) echo "SMOKE TEST FAILED: do NOT release this artifact." ;;
esac
exit $rc
