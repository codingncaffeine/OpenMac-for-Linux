## What's New

- **File ▸ Remove Dropped Disk** — an archive dropped on the window that is too big for a floppy rides in on a disk of its own; this takes that disk off the Mac for good

## What's Fixed

- **A dropped archive's disk came back at every restart** — nothing short of quitting removed it. Dragging its icon to the Trash in the Mac now removes it for good as well, on all four machines
- **Macintosh IIfx: a dropped archive's disk after Restart** — it is on the desktop again after Special ▸ Restart
- **Quadra 950 settings are kept** — its parameter RAM (startup disk, sound volume, monitor settings, the date) was never saved between sessions
- **Macintosh Classic: an empty desktop after startup** — with a second disk attached, a startup could end with no disks on the desktop
- **Mounting, ejecting and flushing wait for the Mac** — the app carries these out when the Macintosh program that is running can take them, which removes rare hangs and crashes inside the Mac, one of them at Reset

## Download

`openmac_0.7.3_amd64.deb` installs on Debian and Ubuntu. `OpenMac-0.7.3-linux-x64.tar.gz` runs anywhere else with glibc: extract it and run `./OpenMac`. `OpenMac-0.7.3-linux-musl-x64.tar.gz` is the same for Alpine. OpenMac contains no original Macintosh code; you supply your own ROM and system disks.
