OpenMac for Linux
=================

A Macintosh emulator written from scratch: Macintosh Classic, Macintosh IIfx,
Quadra 650 and Quadra 950. This is an alpha release.

OpenMac contains no original Macintosh code. You need the ROM of the machine
you want to run, and your own system disks.


Running it
----------

From the tarball: extract it anywhere and run

    ./OpenMac

From the .deb: install it (sudo apt install ./openmac_<version>_amd64.deb) and
start OpenMac from the application menu, or run "openmac".

Then pick the machine in the Machine menu and choose File > Open ROM.
Floppy, hard disk and CD images are attached from the File menu, and
File > Create Hard Disk makes a blank hard disk image.

Click the Mac's screen to give it the mouse and keyboard. While it has them,
desktop shortcuts such as the Super key and Alt+Tab go to the Mac.
Middle-click to give them back to the desktop.


What it needs
-------------

A 64-bit x86 Linux desktop. The app runs as an X11 client (through XWayland
on Wayland sessions). Everything else is in the package, including SDL3 for
sound, which plays through PulseAudio, PipeWire's PulseAudio service, or ALSA.

The tarball needs these from the system, which desktop installs already have:
the C and C++ runtime, ICU, fontconfig and freetype, and the X11 client
libraries (libX11, libICE, libSM, libXi, libXfixes, libXcursor, libXrandr, libXext).
On Alpine use the linux-musl-x64 tarball and install:
    apk add icu-libs libstdc++ libgcc fontconfig libx11 libice libsm libxi libxfixes \
            libxcursor libxrandr libxext


The Macintosh IIfx and the Display Card 8*24 GC
-----------------------------------------------

Without a card ROM the IIfx uses OpenMac's own plain video card. To use the
accelerated Display Card 8*24 GC, choose its declaration ROM (part number
341-0266) with Machine > 8*24 GC Card ROM. For acceleration the Mac's startup
disk also needs the card's own "8*24 GC" control panel in the Control Panels folder
of its System Folder (drag it onto the System Folder and the Finder puts it
there), under its original name. After a restart the rocket climbs the left
edge of the screen during startup.


Where things are kept
---------------------

Settings, parameter RAM and the log:  ~/.config/OpenMac/
The log (openmac.log) is the first thing to attach to a bug report:
https://github.com/codingncaffeine/OpenMac-for-Linux/issues
