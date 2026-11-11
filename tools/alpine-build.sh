#!/usr/bin/env bash
# Builds OpenMac from source on Alpine (musl) in a throwaway container, the way
# an Alpine user would: Alpine's own compiler and .NET SDK, a clean copy of the
# tracked files, warnings as errors, then the core's tests.
#   tools/alpine-build.sh [alpine tag, default latest]
set -uo pipefail
cd "$(dirname "$0")/.."
tag="${1:-latest}"
out=scratch/alpine
mkdir -p "$out"
src=$(mktemp -d "$PWD/$out/src.XXXXXX")
git archive HEAD | tar -x -C "$src"
# Uncommitted changes to tracked files too, so the check covers what is about to be committed.
git diff HEAD --binary | (cd "$src" && git apply --allow-empty 2>/dev/null || true)
JOBS="${OPENMAC_JOBS:-$(( ($(nproc) + 3) / 4 ))}"
nice -n 10 podman run --rm --network=host -e JOBS="$JOBS" -v "$src:/src:Z" -w /src "docker.io/library/alpine:$tag" sh -euc '
    apk add --no-cache -q build-base cmake samurai dotnet10-sdk icu-libs > /dev/null
    echo "── Alpine $(cat /etc/alpine-release), $(c++ --version | head -1), .NET $(dotnet --version)"
    cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DOPENMAC_BUILD_SHELL=OFF > /dev/null
    cmake --build build --parallel "$JOBS" | tail -1
    ctest --test-dir build --output-on-failure -j "$JOBS" | grep -E "tests passed|tests failed|\*\*\*Failed"
    dotnet build gui -c Release --nologo -v q 2>&1 | grep -E "error|warn|Warn|Error" | sort -u
    test -f gui/bin/Release/net10.0/libopenmac_c.so && echo "core library beside the app: yes"
' > "$out/build.log" 2>&1
rc=$?
cat "$out/build.log"
rm -rf "$src"
if [ $rc -eq 0 ] && grep -q "100% tests passed" "$out/build.log" && grep -q " 0 Error(s)" "$out/build.log" \
     && grep -q " 0 Warning(s)" "$out/build.log" && grep -q "core library beside the app: yes" "$out/build.log"; then
  echo "ALPINE BUILD PASSED"
else
  echo "ALPINE BUILD FAILED"; exit 1
fi
