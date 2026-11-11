#!/bin/sh
# Runs INSIDE a build container (packaging/build-release.sh starts it): builds the
# two native libraries a release ships beside the app, into /out.
#
#   libopenmac_c.so   the emulator core, with the C++ runtime linked in, so the
#                     only thing it needs from the system is the C library
#   libSDL3.so.0      SDL3 for sound output only (PulseAudio and ALSA, opened at
#                     run time). Debian and Ubuntu LTS have no usable SDL3 package.
#
# The glibc build runs in manylinux_2_28 (glibc 2.28, a current GCC), so the
# libraries load on every mainstream distro; the musl build runs in Alpine.
# /src is the repository (read-only); /cache keeps the SDL3 source archive and
# the SDL3 library built from it.
set -eu
JOBS="${JOBS:-4}"
SDL_VER=3.4.16
SDL_SHA256=7322236cd12090c3eb40b9728be4d49c76f66ad17d04369584d4ecad5cf77c68

LIBC=glibc; command -v apk >/dev/null && LIBC=musl
SDL_BUILT="/cache/libSDL3-$SDL_VER-$LIBC.so.0"
if command -v apk >/dev/null; then
  apk add --no-cache -q build-base cmake samurai curl >/dev/null
  [ -f "$SDL_BUILT" ] || apk add --no-cache -q alsa-lib-dev pulseaudio-dev linux-headers >/dev/null
elif command -v dnf >/dev/null; then
  [ -f "$SDL_BUILT" ] || dnf install -y -q alsa-lib-devel pulseaudio-libs-devel >/dev/null
fi
GEN=""; command -v ninja >/dev/null && GEN="-G Ninja"

mkdir -p /work/gui/native
cp -a /src/CMakeLists.txt /src/core /work/
cmake -S /work -B /work/build $GEN -DCMAKE_BUILD_TYPE=Release \
      -DOPENMAC_BUILD_SHELL=OFF -DOPENMAC_BUILD_TESTS=OFF \
      -DCMAKE_SHARED_LINKER_FLAGS="-static-libstdc++ -static-libgcc" >/dev/null
cmake --build /work/build --target openmac_c --parallel "$JOBS" | tail -1
cp /work/gui/native/libopenmac_c.so /out/

# SDL3 changes only when the pin above does, so the built library is kept in the
# cache folder and reused; the sound headers are installed only for a rebuild.
if [ ! -f "$SDL_BUILT" ]; then
  TGZ="/cache/SDL3-$SDL_VER.tar.gz"
  [ -f "$TGZ" ] || curl -fsSL -o "$TGZ" "https://github.com/libsdl-org/SDL/releases/download/release-$SDL_VER/SDL3-$SDL_VER.tar.gz"
  echo "$SDL_SHA256  $TGZ" | sha256sum -c - >/dev/null
  tar -xzf "$TGZ" -C /work
  cmake -S "/work/SDL3-$SDL_VER" -B /work/sdl $GEN -DCMAKE_BUILD_TYPE=Release \
      -DSDL_SHARED=ON -DSDL_STATIC=OFF -DSDL_TEST_LIBRARY=OFF -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF \
      -DSDL_INSTALL=OFF -DSDL_INSTALL_DOCS=OFF \
      -DSDL_PULSEAUDIO=ON -DSDL_PULSEAUDIO_SHARED=ON -DSDL_ALSA=ON -DSDL_ALSA_SHARED=ON \
      -DSDL_PIPEWIRE=OFF -DSDL_JACK=OFF -DSDL_SNDIO=OFF -DSDL_OSS=OFF \
      -DSDL_X11=OFF -DSDL_WAYLAND=OFF -DSDL_KMSDRM=OFF -DSDL_OPENGL=OFF -DSDL_OPENGLES=OFF \
      -DSDL_VULKAN=OFF -DSDL_RENDER_GPU=OFF -DSDL_RENDER_VULKAN=OFF -DSDL_OPENVR=OFF \
      -DSDL_RPI=OFF -DSDL_ROCKCHIP=OFF -DSDL_VIVANTE=OFF \
      -DSDL_HIDAPI=OFF -DSDL_HIDAPI_LIBUSB=OFF -DSDL_LIBUDEV=OFF -DSDL_DBUS=OFF \
      -DSDL_IBUS=OFF -DSDL_FRIBIDI=OFF -DSDL_LIBTHAI=OFF -DSDL_LIBURING=OFF \
      -DSDL_UNIX_CONSOLE_BUILD=ON > /work/sdl-configure.log 2>&1 || { tail -30 /work/sdl-configure.log; exit 1; }
  cmake --build /work/sdl --parallel "$JOBS" > /work/sdl-build.log 2>&1 || { tail -40 /work/sdl-build.log; exit 1; }
  cp -L /work/sdl/libSDL3.so.0 "$SDL_BUILT.tmp"
  strip --strip-unneeded "$SDL_BUILT.tmp"
  mv "$SDL_BUILT.tmp" "$SDL_BUILT"
fi
cp "$SDL_BUILT" /out/libSDL3.so.0
strip --strip-unneeded /out/libopenmac_c.so
ls -la /out
