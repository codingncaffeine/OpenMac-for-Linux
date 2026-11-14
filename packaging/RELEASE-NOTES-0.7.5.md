## What's New

- **Macintosh SE/30** — a fifth machine: a 16 MHz 68030 with its 68882, the built-in 512×342 black-and-white screen, 1 to 128 MB of RAM, the internal SuperDrive, hard disks and a CD-ROM drive on its SCSI bus, sound, and Shut Down and Restart from the Special menu. It starts System 6.0.8, 7.0.1, 7.1 and 7.5 from a floppy or a hard disk. Choose it under Machine ▸ Model and open the 256 KB ROM with checksum `97221136` (the one the Macintosh IIx and IIcx share)
- **The SE/30's video ROM is optional** — the machine starts on OpenMac's own; Machine ▸ Video ROM… takes the original 8 KB file if you have it
- **More than 8 MB on the SE/30** — with System 7.1 and the 32-Bit System Enabler in the System Folder, and 32-bit addressing switched on in the Memory control panel, the System uses all of 16 to 80 MB

## Known Problems

All of these are on the SE/30.

- **System 7.5 can stop with a system error when an Apple menu item is chosen** (“Finder”, illegal instruction or address error). It happens when the first click in the menu bar after start-up missed every menu (on the clock, on the empty part of the bar, left of the Apple) or was a very short tap on a menu's title. The fault is in System 7.5's Apple Menu Options control panel meeting a flaw in this ROM, not in the machine: the same disk on the Macintosh IIfx is not affected. To avoid it for good, open the Apple Menu Options control panel and set Submenus to Off; without that, open any menu once after each start-up
- **A start with System 7.5's Install Disk 1 in the drive and a hard disk that already holds System 7.5 ended in a system error once.** It has not happened again in tests. After an installation, start without the floppy in the drive
- **System 6 does not keep a read-only disk on its desktop** — an archive too big for a floppy dropped on the window, or a second disk attached from a file the app may not write. System 7 and later show both
- **128 MB with the 32-Bit System Enabler does not start.** Without the Enabler 128 MB starts and the System uses 8 MB; with it, use 80 MB or less
- **It runs a little fast**: 1.5% on processor work, 4.5% on drawing, 2.3% on arithmetic, measured against a real machine's published benchmark figures
- **Sound from the headphone jack is not played in stereo**: the app plays what the built-in speaker would

## Download

`openmac_0.7.5_amd64.deb` installs on Debian and Ubuntu. `OpenMac-0.7.5-linux-x64.tar.gz` runs anywhere else with glibc: extract it and run `./OpenMac`. `OpenMac-0.7.5-linux-musl-x64.tar.gz` is the same for Alpine. OpenMac contains no original Macintosh code; you supply your own ROM and system disks.
