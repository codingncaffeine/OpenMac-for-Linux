#!/usr/bin/env bash
# Builds the native core and the app, runs the core's tests, and refreshes the
# runnable dev build in bin/ at the top of the repo:
#
#   tools/build.sh            then run   bin/openmac
#   tools/build.sh --no-test  skip the core's tests
#
# Uses a quarter of the cores at low priority unless OPENMAC_JOBS says otherwise.
set -euo pipefail
cd "$(dirname "$0")/.."
JOBS="${OPENMAC_JOBS:-$(( ($(nproc) + 3) / 4 ))}"
NICE=(nice -n 10)
command -v taskset >/dev/null && NICE=(taskset -c "0-$((JOBS - 1))" nice -n 10)
if ! command -v dotnet >/dev/null && [ -x "$HOME/.dotnet/dotnet" ]; then
  export DOTNET_ROOT="$HOME/.dotnet" PATH="$HOME/.dotnet:$PATH"
fi

GEN=(); command -v ninja >/dev/null && GEN=(-G Ninja)
[ -f build/CMakeCache.txt ] || cmake -S . -B build "${GEN[@]}" -DCMAKE_BUILD_TYPE=Release -DOPENMAC_BUILD_SHELL=OFF
"${NICE[@]}" cmake --build build --parallel "$JOBS"
[ "${1:-}" = "--no-test" ] || "${NICE[@]}" ctest --test-dir build --output-on-failure -j "$JOBS"
"${NICE[@]}" dotnet build gui -c Release -v q --nologo

# bin/app is the build output; bin/openmac is the one thing to run.
rm -rf bin/app && mkdir -p bin/app
cp -a gui/bin/Release/net10.0/. bin/app/
cat > bin/openmac <<'LAUNCH'
#!/bin/sh
exec "$(dirname "$(readlink -f "$0")")/app/OpenMac" "$@"
LAUNCH
chmod +x bin/openmac
test -f bin/app/libopenmac_c.so || { echo "build: the native core is missing from bin/app" >&2; exit 1; }
echo "build: ok -> bin/openmac"
