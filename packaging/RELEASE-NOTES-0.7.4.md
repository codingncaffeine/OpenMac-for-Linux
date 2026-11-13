A hotfix for 0.7.3.

## What's Fixed

- **Dropping an archive on the Quadra 650 or the Quadra 950** — after the restart that makes the dropped disk appear, the Mac never finished starting and played a continuous tone, and every restart with the disk attached did the same. 0.7.3 introduced this; the Mac starts with the disk on its desktop again

## Download

`openmac_0.7.4_amd64.deb` installs on Debian and Ubuntu. `OpenMac-0.7.4-linux-x64.tar.gz` runs anywhere else with glibc: extract it and run `./OpenMac`. `OpenMac-0.7.4-linux-musl-x64.tar.gz` is the same for Alpine. OpenMac contains no original Macintosh code; you supply your own ROM and system disks.
