## What's New

The first alpha of OpenMac for Linux: the same emulator core as OpenMac, with a native Linux front end.

- **Three machines** — the Macintosh Classic, the Macintosh IIfx and the Quadra 650, each remembering its own ROM, disks, RAM and display
- **Display Card 8•24 GC on the IIfx** — supply the card's ROM and its control panel, and the accelerator draws the desktop, rocket and all
- **Captured mouse and keyboard** — click the Mac's screen and the pointer stays inside it, with Super, Alt+Tab and the other desktop shortcuts going to the Mac; middle-click gives them back
- **Sound** — through PulseAudio, PipeWire or ALSA, with nothing extra to install
- **Floppies, hard disks, CD images, host folders and the drop box** — the same media handling as on Windows
- **Packages** — a `.deb` for Debian and Ubuntu, a tarball for any other glibc distro, and a tarball for Alpine and other musl systems

## What's Fixed

- A Macintosh Classic with a hard disk attached no longer crashes or shows a sad Mac while starting from certain floppies
- A Macintosh IIfx without a card ROM no longer stops at a gray screen before the pointer appears

## Download

`openmac_0.0.3_amd64.deb` installs on Debian and Ubuntu. `OpenMac-0.0.3-linux-x64.tar.gz` runs anywhere else with glibc: extract it and run `./OpenMac`. `OpenMac-0.0.3-linux-musl-x64.tar.gz` is the same for Alpine. OpenMac contains no original Macintosh code; you supply your own ROM and system disks.
