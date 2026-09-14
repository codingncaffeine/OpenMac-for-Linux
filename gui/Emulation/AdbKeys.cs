using Avalonia.Input;

namespace OpenMac.Gui.Emulation;

/// <summary>Physical key -> Apple ADB keycode. ADB codes name positions on the
/// keyboard, not characters, so the host key is taken by position too: the key
/// where US-layout Q sits is ADB $0C whatever the host layout prints on it, and
/// the guest's own keyboard layout decides what it types.
/// These are the RAW codes the keyboard puts on the ADB bus, which the System's
/// KMAP turns into the virtual key codes applications see -- the two differ for
/// Control (raw $36, virtual $3B) and the arrows (raw $3B-$3E, virtual $7B-$7E).
/// Sending the virtual codes pressed the Extended keyboard's raw $7B/$7D/$7E,
/// its right-hand Shift/Option/Control, so the arrows acted as modifiers.</summary>
internal static class AdbKeys
{
    public static int Map(PhysicalKey k) => k switch
    {
        PhysicalKey.A => 0x00, PhysicalKey.S => 0x01, PhysicalKey.D => 0x02, PhysicalKey.F => 0x03,
        PhysicalKey.H => 0x04, PhysicalKey.G => 0x05, PhysicalKey.Z => 0x06, PhysicalKey.X => 0x07,
        PhysicalKey.C => 0x08, PhysicalKey.V => 0x09, PhysicalKey.IntlBackslash => 0x0A,
        PhysicalKey.B => 0x0B, PhysicalKey.Q => 0x0C, PhysicalKey.W => 0x0D, PhysicalKey.E => 0x0E,
        PhysicalKey.R => 0x0F, PhysicalKey.Y => 0x10, PhysicalKey.T => 0x11, PhysicalKey.O => 0x1F,
        PhysicalKey.U => 0x20, PhysicalKey.I => 0x22, PhysicalKey.P => 0x23, PhysicalKey.L => 0x25,
        PhysicalKey.J => 0x26, PhysicalKey.K => 0x28, PhysicalKey.N => 0x2D, PhysicalKey.M => 0x2E,
        PhysicalKey.Digit1 => 0x12, PhysicalKey.Digit2 => 0x13, PhysicalKey.Digit3 => 0x14,
        PhysicalKey.Digit4 => 0x15, PhysicalKey.Digit5 => 0x17, PhysicalKey.Digit6 => 0x16,
        PhysicalKey.Digit7 => 0x1A, PhysicalKey.Digit8 => 0x1C, PhysicalKey.Digit9 => 0x19,
        PhysicalKey.Digit0 => 0x1D,
        PhysicalKey.Enter => 0x24, PhysicalKey.Tab => 0x30, PhysicalKey.Space => 0x31,
        PhysicalKey.Backspace => 0x33, PhysicalKey.Escape => 0x35,
        PhysicalKey.Minus => 0x1B, PhysicalKey.Equal => 0x18, PhysicalKey.Comma => 0x2B,
        PhysicalKey.Period => 0x2F, PhysicalKey.Slash => 0x2C, PhysicalKey.Semicolon => 0x29,
        PhysicalKey.Quote => 0x27, PhysicalKey.BracketLeft => 0x21, PhysicalKey.BracketRight => 0x1E,
        PhysicalKey.Backslash => 0x2A, PhysicalKey.Backquote => 0x32, PhysicalKey.Delete => 0x75,
        PhysicalKey.ArrowLeft => 0x3B, PhysicalKey.ArrowRight => 0x3C,
        PhysicalKey.ArrowDown => 0x3D, PhysicalKey.ArrowUp => 0x3E,
        PhysicalKey.ShiftLeft or PhysicalKey.ShiftRight => 0x38, PhysicalKey.CapsLock => 0x39,
        PhysicalKey.ControlLeft or PhysicalKey.ControlRight => 0x36,
        PhysicalKey.AltLeft or PhysicalKey.AltRight => 0x3A,
        PhysicalKey.MetaLeft or PhysicalKey.MetaRight => 0x37,
        // Keypad (the emulated keyboard reports itself as an extended ADB
        // keyboard, so the full keypad is fair game; 0x5A is unused on Apple)
        PhysicalKey.NumPad0 => 0x52, PhysicalKey.NumPad1 => 0x53, PhysicalKey.NumPad2 => 0x54,
        PhysicalKey.NumPad3 => 0x55, PhysicalKey.NumPad4 => 0x56, PhysicalKey.NumPad5 => 0x57,
        PhysicalKey.NumPad6 => 0x58, PhysicalKey.NumPad7 => 0x59, PhysicalKey.NumPad8 => 0x5B,
        PhysicalKey.NumPad9 => 0x5C, PhysicalKey.NumPadDecimal => 0x41,
        PhysicalKey.NumPadMultiply => 0x43, PhysicalKey.NumPadAdd => 0x45,
        PhysicalKey.NumPadDivide => 0x4B, PhysicalKey.NumPadSubtract => 0x4E,
        PhysicalKey.NumPadEnter => 0x4C, PhysicalKey.NumPadEqual => 0x51,
        PhysicalKey.NumLock or PhysicalKey.NumPadClear => 0x47,   // Clear
        // Function and navigation keys (F11 is the host's fullscreen toggle)
        PhysicalKey.F1 => 0x7A, PhysicalKey.F2 => 0x78, PhysicalKey.F3 => 0x63, PhysicalKey.F4 => 0x76,
        PhysicalKey.F5 => 0x60, PhysicalKey.F6 => 0x61, PhysicalKey.F7 => 0x62, PhysicalKey.F8 => 0x64,
        PhysicalKey.F9 => 0x65, PhysicalKey.F10 => 0x6D, PhysicalKey.F12 => 0x6F,
        PhysicalKey.Home => 0x73, PhysicalKey.End => 0x77,
        PhysicalKey.PageUp => 0x74, PhysicalKey.PageDown => 0x79,
        PhysicalKey.Insert or PhysicalKey.Help => 0x72,    // Help
        _ => -1,
    };
}
