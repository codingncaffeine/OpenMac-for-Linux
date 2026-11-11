#!/usr/bin/env bash
# Runs a command the way every GUI test of OpenMac must run: on a virtual X
# server (no window on the desktop), on its own D-Bus session that can start
# nothing, with private XDG folders (never the real ~/.config/OpenMac), and with
# sound made impossible (tools/silent.sh).
#
#   tools/headless.sh COMMAND [ARGS...]
#   OPENMAC_TEST_HOME=DIR tools/headless.sh ...   keep the scratch profile in DIR (default: a temp dir, removed)
#   OPENMAC_TEST_SCREEN=1280x1024x24              the virtual screen
set -euo pipefail
[ $# -ge 1 ] || { sed -n '2,9p' "$0"; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${OPENMAC_TEST_HOME:-}" ]; then
  TMP="$(realpath -m "$OPENMAC_TEST_HOME")"; mkdir -p "$TMP"
else
  TMP="$(mktemp -d "${TMPDIR:-/tmp}/openmac-headless.XXXXXX")"
  trap 'rm -rf "$TMP"' EXIT
fi
mkdir -p "$TMP/config" "$TMP/data" "$TMP/state" "$TMP/cache" "$TMP/rt"; chmod 700 "$TMP/rt"
export XDG_CONFIG_HOME="$TMP/config" XDG_DATA_HOME="$TMP/data" XDG_STATE_HOME="$TMP/state" \
       XDG_CACHE_HOME="$TMP/cache" XDG_RUNTIME_DIR="$TMP/rt"
export NO_AT_BRIDGE=1 GDK_BACKEND=x11
unset WAYLAND_DISPLAY DISPLAY
"$HERE/silent.sh" xvfb-run -a -s "-screen 0 ${OPENMAC_TEST_SCREEN:-1280x1024x24}" \
  dbus-run-session --config-file="$HERE/isolated-bus.conf" -- "$@"
