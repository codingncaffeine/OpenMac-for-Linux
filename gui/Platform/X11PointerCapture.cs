using System.Runtime.InteropServices;
using Avalonia.Platform;

namespace OpenMac.Gui.Platform;

/// <summary>
/// Captured mouse for a window on X11 (including Xwayland under a Wayland
/// desktop). While locked, the Mac is fed the mouse's own relative motion from
/// XInput2 raw events, and the hidden host pointer is warped back to the window
/// centre so it never reaches an edge. Under Xwayland a warp of a hidden pointer
/// is what engages the compositor's pointer lock, so the pointer cannot leave
/// the window at all.
///
/// Raw events are the X11 counterpart of the Windows build's Raw Input: they
/// carry device counts before pointer acceleration, and warping the pointer
/// manufactures none of them, so the warp-back never reads as motion.
///
/// Everything here runs on one thread that owns a private X connection. The UI
/// only flips the lock on and off and collects the accumulated motion, so no Xlib
/// call is ever made from two threads and Avalonia's own connection is untouched.
/// Buttons are left alone: nothing is grabbed, so clicks still reach the window.
/// </summary>
internal sealed class X11PointerCapture : IDisposable
{
    private const int GenericEvent = 35;
    private const int XI_RawMotion = 17;
    private const int XIAllMasterDevices = 1;
    private const short POLLIN = 1;

    [StructLayout(LayoutKind.Sequential)]
    private struct XIEventMask
    {
        public int deviceid;
        public int mask_len;
        public IntPtr mask;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct XGenericEventCookie
    {
        public int type;
        public nuint serial;
        public int send_event;
        public IntPtr display;
        public int extension;
        public int evtype;
        public uint cookie;
        public IntPtr data;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct XIRawEvent
    {
        public int type;
        public nuint serial;
        public int send_event;
        public IntPtr display;
        public int extension;
        public int evtype;
        public nuint time;
        public int deviceid;
        public int sourceid;
        public int detail;
        public int flags;
        public int valuators_mask_len;
        public IntPtr valuators_mask;
        public IntPtr valuators_values;
        public IntPtr raw_values;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PollFd
    {
        public int fd;
        public short events;
        public short revents;
    }

    private const string X11 = "libX11.so.6";
    private const string Xi = "libXi.so.6";

    [DllImport(X11)] private static extern IntPtr XOpenDisplay(IntPtr name);
    [DllImport(X11)] private static extern int XCloseDisplay(IntPtr dpy);
    [DllImport(X11)] private static extern nuint XDefaultRootWindow(IntPtr dpy);
    [DllImport(X11)] private static extern int XConnectionNumber(IntPtr dpy);
    [DllImport(X11)] private static extern int XPending(IntPtr dpy);
    [DllImport(X11)] private static extern int XNextEvent(IntPtr dpy, IntPtr ev);
    [DllImport(X11)] private static extern int XFlush(IntPtr dpy);
    [DllImport(X11)] private static extern int XQueryExtension(IntPtr dpy, string name, out int opcode, out int evt, out int err);
    [DllImport(X11)] private static extern int XGetEventData(IntPtr dpy, IntPtr cookie);
    [DllImport(X11)] private static extern void XFreeEventData(IntPtr dpy, IntPtr cookie);
    [DllImport(X11)] private static extern int XWarpPointer(IntPtr dpy, nuint src, nuint dest, int sx, int sy, uint sw, uint sh, int dx, int dy);
    [DllImport(X11)] private static extern int XGetGeometry(IntPtr dpy, nuint drawable, out nuint root, out int x, out int y,
                                                            out uint width, out uint height, out uint border, out uint depth);
    [DllImport(X11)] private static extern int XQueryPointer(IntPtr dpy, nuint window, out nuint root, out nuint child,
                                                             out int rootX, out int rootY, out int winX, out int winY, out uint mask);
    [DllImport(Xi)] private static extern int XIQueryVersion(IntPtr dpy, ref int major, ref int minor);
    [DllImport(Xi)] private static extern int XISelectEvents(IntPtr dpy, nuint window, ref XIEventMask masks, int count);
    [DllImport("libc")] private static extern int poll(ref PollFd fds, nuint nfds, int timeout);

    private readonly nuint _window;
    private readonly Action<string> _log;
    private readonly Thread _thread;
    private readonly object _motionLock = new();
    private volatile bool _wantLocked;
    private volatile bool _stop;
    private double _dx, _dy;

    // Instruments, reset at every lock. Raw packets say the device path is alive;
    // the farthest the pointer was ever seen from centre says whether the lock
    // held -- a pointer that escapes shows up as a distance of hundreds of pixels.
    private long _rawPackets, _warps, _pointerSamples, _outsideSamples;
    private double _maxDistance;

    private X11PointerCapture(nuint window, Action<string> log)
    {
        _window = window;
        _log = log;
        _thread = new Thread(Run) { IsBackground = true, Name = "OpenMac-PointerCapture" };
    }

    /// <summary>A capture for this window, or null when it is not an X11 window
    /// or the X server has no XInput2.</summary>
    public static X11PointerCapture? TryCreate(IPlatformHandle? handle, Action<string> log)
    {
        if (handle is null || handle.HandleDescriptor != "XID") return null;
        var capture = new X11PointerCapture((nuint)(ulong)handle.Handle, log);
        using var ready = new ManualResetEventSlim();
        bool ok = false;
        capture._thread.Start((Action<bool>)(result => { ok = result; ready.Set(); }));
        ready.Wait();
        if (ok) return capture;
        capture.Dispose();
        return null;
    }

    public void Lock()
    {
        lock (_motionLock) { _dx = _dy = 0; }
        Interlocked.Exchange(ref _rawPackets, 0);
        Interlocked.Exchange(ref _warps, 0);
        Interlocked.Exchange(ref _pointerSamples, 0);
        Interlocked.Exchange(ref _outsideSamples, 0);
        _maxDistance = 0;
        _wantLocked = true;
    }

    public void Unlock() => _wantLocked = false;

    /// <summary>Motion gathered since the last call, in device counts.</summary>
    public void TakeMotion(out double dx, out double dy)
    {
        lock (_motionLock)
        {
            dx = _dx; dy = _dy;
            _dx = _dy = 0;
        }
    }

    public string Stats() =>
        $"raw={Interlocked.Read(ref _rawPackets)} warps={Interlocked.Read(ref _warps)} "
        + $"pointerSamples={Interlocked.Read(ref _pointerSamples)} outside={Interlocked.Read(ref _outsideSamples)} "
        + $"maxFromCentre={_maxDistance:0}px";

    private void Run(object? state)
    {
        var started = (Action<bool>)state!;
        IntPtr dpy = XOpenDisplay(IntPtr.Zero);
        if (dpy == IntPtr.Zero)
        {
            _log("input: pointer capture unavailable -- could not open the X display");
            started(false);
            return;
        }
        IntPtr ev = Marshal.AllocHGlobal(192);        // sizeof(XEvent) on 64-bit
        IntPtr maskBytes = Marshal.AllocHGlobal(4);
        try
        {
            int major = 2, minor = 2;
            if (XQueryExtension(dpy, "XInputExtension", out int opcode, out _, out _) == 0 ||
                XIQueryVersion(dpy, ref major, ref minor) != 0)
            {
                _log("input: pointer capture unavailable -- the X server has no XInput2");
                started(false);
                return;
            }
            nuint root = XDefaultRootWindow(dpy);
            int fd = XConnectionNumber(dpy);
            _log($"input: X11 pointer capture ready (XInput {major}.{minor}, window 0x{(ulong)_window:X})");
            started(true);

            bool selected = false;
            long nextGeometry = 0, nextSample = 0;
            int cx = 0, cy = 0, width = 0, height = 0;
            var watch = System.Diagnostics.Stopwatch.StartNew();

            while (!_stop)
            {
                bool want = _wantLocked;
                if (want != selected)
                {
                    // Raw motion is only asked for while the mouse is captured.
                    Marshal.WriteInt32(maskBytes, want ? 1 << XI_RawMotion : 0);
                    var mask = new XIEventMask { deviceid = XIAllMasterDevices, mask_len = 4, mask = maskBytes };
                    XISelectEvents(dpy, root, ref mask, 1);
                    selected = want;
                    nextGeometry = 0;
                    if (!want) XFlush(dpy);
                }

                bool moved = false;
                while (XPending(dpy) > 0)
                {
                    XNextEvent(dpy, ev);
                    var cookie = Marshal.PtrToStructure<XGenericEventCookie>(ev);
                    if (cookie.type != GenericEvent || cookie.extension != opcode) continue;
                    if (XGetEventData(dpy, ev) == 0) continue;
                    try
                    {
                        cookie = Marshal.PtrToStructure<XGenericEventCookie>(ev);
                        if (cookie.evtype == XI_RawMotion && selected && _wantLocked)
                        {
                            ReadRawMotion(Marshal.PtrToStructure<XIRawEvent>(cookie.data));
                            moved = true;
                        }
                    }
                    finally { XFreeEventData(dpy, ev); }
                }

                if (selected)
                {
                    long now = watch.ElapsedMilliseconds;
                    if (now >= nextGeometry)
                    {
                        // The window can be resized while captured; keep the centre current.
                        if (XGetGeometry(dpy, _window, out _, out _, out _, out uint w, out uint h, out _, out _) != 0)
                        {
                            width = (int)w; height = (int)h;
                            cx = width / 2; cy = height / 2;
                        }
                        nextGeometry = now + 250;
                        moved = true;   // warp at once on capture and after a resize
                    }
                    if (moved && width > 0)
                    {
                        if (now >= nextSample)
                        {
                            if (XQueryPointer(dpy, _window, out _, out _, out _, out _, out int px, out int py, out _) != 0)
                            {
                                Interlocked.Increment(ref _pointerSamples);
                                if (px < 0 || py < 0 || px >= width || py >= height)
                                    Interlocked.Increment(ref _outsideSamples);
                                double d = Math.Sqrt((double)(px - cx) * (px - cx) + (double)(py - cy) * (py - cy));
                                if (d > _maxDistance) _maxDistance = d;
                            }
                            nextSample = now + 50;
                        }
                        XWarpPointer(dpy, 0, _window, 0, 0, 0, 0, cx, cy);
                        XFlush(dpy);
                        Interlocked.Increment(ref _warps);
                    }
                }

                var pfd = new PollFd { fd = fd, events = POLLIN };
                poll(ref pfd, 1, selected ? 4 : 50);
            }
        }
        catch (Exception ex)
        {
            _log("input: pointer capture thread failed -- " + ex.Message);
        }
        finally
        {
            Marshal.FreeHGlobal(maskBytes);
            Marshal.FreeHGlobal(ev);
            XCloseDisplay(dpy);
        }
    }

    // The valuator mask names which axes the event carries; their values are
    // packed in mask order. Axis 0 is X and axis 1 is Y on every pointer.
    private void ReadRawMotion(XIRawEvent raw)
    {
        double dx = 0, dy = 0;
        int index = 0;
        int bits = raw.valuators_mask_len * 8;
        for (int axis = 0; axis < bits && axis <= 1; axis++)
        {
            byte b = Marshal.ReadByte(raw.valuators_mask, axis / 8);
            if ((b & (1 << (axis % 8))) == 0) continue;
            double value = BitConverter.Int64BitsToDouble(Marshal.ReadInt64(raw.raw_values, index * 8));
            if (axis == 0) dx = value;
            else dy = value;
            index++;
        }
        Interlocked.Increment(ref _rawPackets);
        lock (_motionLock) { _dx += dx; _dy += dy; }
    }

    public void Dispose()
    {
        _wantLocked = false;
        _stop = true;
        if (_thread.IsAlive) _thread.Join(1000);
    }
}
