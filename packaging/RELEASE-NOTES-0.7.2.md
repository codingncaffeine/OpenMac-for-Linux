## What's New

- **Macintosh Quadra 950** — a fourth machine: a 33 MHz 68040 with 8 to 256 MB of RAM, 1 or 2 MB of video RAM (millions of colors up to 832×624), six displays, two SCSI buses, the internal SuperDrive, sound, and Shut Down and Restart from the Special menu. It starts System 7.5 and Mac OS 8.1 from a hard disk or a CD. Choose it under Machine ▸ Model and open the 1 MB Quadra 950 ROM (checksum `3DC27823`)
- **1 GB hard disks** — File ▸ Create Hard Disk has a 1 GB size for the Quadra 950
- **400K and 800K floppies on the Macintosh IIfx** — the two older disk sizes are read in the SuperDrive, as they are on the Quadra 950

## What's Fixed

- **Eject on the Macintosh IIfx** — after File ▸ Eject, the next floppy inserted is no longer thrown back out
- **Writing to 1.44 MB floppies on the Macintosh IIfx** — what the Mac wrote never reached the image file; it does now
- **12-inch RGB and 21-inch Color displays on the Quadra 650** — the 12-inch drew at half height and the 21-inch came up in black and white. Both are right now; a Quadra 650 set to either starts once with fresh monitor settings
- **Thousands of colors on the Quadra 650** — the colors now match the 256-color picture
- **The window stays on the display** when the Mac's screen changes size, instead of growing past the edge to where it could not be moved
- **A CD chosen before a ROM is open** is kept and goes into the drive when the ROM is opened
- **ROM and disk files reached through a symbolic link** are accepted

## Download

`openmac_0.7.2_amd64.deb` installs on Debian and Ubuntu. `OpenMac-0.7.2-linux-x64.tar.gz` runs anywhere else with glibc: extract it and run `./OpenMac`. `OpenMac-0.7.2-linux-musl-x64.tar.gz` is the same for Alpine. OpenMac contains no original Macintosh code; you supply your own ROM and system disks.
