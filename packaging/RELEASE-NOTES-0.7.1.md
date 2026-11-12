## What's New

- **Start up from a CD on the Quadra 650** — a Mac OS install CD starts the machine and installs onto a blank hard disk. A hard disk that already has a System on it still starts first, as on the real machine
- **Thousands of colors on the Quadra 650** — on the 13-inch (640×480) and 16-inch (832×624) displays; choose it in the Monitors control panel
- **The Mac's own CD-ROM software runs the drive on the Quadra 650** — the driver on a startup disc and the System's CD-ROM extension both work; OpenMac's built-in driver steps in only when the System has none
- **One version number** — OpenMac for Linux and OpenMac for Windows are both 0.7.1; the previous Linux release was 0.0.3

## What's Fixed

- **Restart from inside the Mac on the Quadra 650** — an installer's Restart button or Special ▸ Restart with a CD and a second disk attached no longer ends at the sad Mac
- **Restart on the Macintosh IIfx** — with a second disk or a host folder attached, a restart no longer stops at "Welcome to Macintosh"
- **The CD stays in across a restart** on the Quadra 650, so a System that restarts during startup comes back to its disc

## Download

`openmac_0.7.1_amd64.deb` installs on Debian and Ubuntu. `OpenMac-0.7.1-linux-x64.tar.gz` runs anywhere else with glibc: extract it and run `./OpenMac`. `OpenMac-0.7.1-linux-musl-x64.tar.gz` is the same for Alpine. OpenMac contains no original Macintosh code; you supply your own ROM and system disks.
