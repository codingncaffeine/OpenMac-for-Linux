using System.Runtime.InteropServices;

namespace OpenMac.Gui.Emulation;

/// <summary>
/// Streaming audio sink over an SDL3 audio stream (PipeWire, PulseAudio or ALSA,
/// whichever SDL finds). The emulated Mac produces 8-bit unsigned mono PCM at
/// ~22254 Hz, drained once per guest frame on the emulation thread. SDL resamples
/// to the device rate and pulls on its own thread, so this side only queues.
///
/// Same surface as the Windows waveOut sink, so the machine backends drive it
/// unchanged: Feed per frame, Stats once a second, Dispose on the way out.
///
/// Two bounds keep playback smooth without letting latency grow. Playback starts
/// only once a small cushion is queued, so the per-frame jitter of the producer
/// does not reach the device as gaps. And the queue is capped: the guest's clock
/// and the sound card's never agree exactly, so a producer running slightly fast
/// would otherwise build delay without limit. Samples that would push the queue
/// past the cap are dropped and counted.
/// </summary>
internal sealed class WaveAudio : IDisposable
{
    private const uint SDL_INIT_AUDIO = 0x00000010;
    private const uint SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK = 0xFFFFFFFF;
    private const int SDL_AUDIO_U8 = 0x0008;

    [StructLayout(LayoutKind.Sequential)]
    private struct SDL_AudioSpec
    {
        public int format;
        public int channels;
        public int freq;
    }

    [DllImport("SDL3")] [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SDL_SetAppMetadata(string appname, string appversion, string appidentifier);
    [DllImport("SDL3")] [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SDL_InitSubSystem(uint flags);
    [DllImport("SDL3")] private static extern void SDL_QuitSubSystem(uint flags);
    [DllImport("SDL3")]
    private static extern IntPtr SDL_OpenAudioDeviceStream(uint devid, in SDL_AudioSpec spec, IntPtr callback, IntPtr userdata);
    [DllImport("SDL3")] [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SDL_ResumeAudioStreamDevice(IntPtr stream);
    [DllImport("SDL3")] [return: MarshalAs(UnmanagedType.I1)]
    private static extern bool SDL_PutAudioStreamData(IntPtr stream, byte[] buf, int len);
    [DllImport("SDL3")] private static extern int SDL_GetAudioStreamQueued(IntPtr stream);
    [DllImport("SDL3")] private static extern void SDL_DestroyAudioStream(IntPtr stream);
    [DllImport("SDL3")] private static extern IntPtr SDL_GetError();

    private readonly int _rate;
    private readonly bool _sdlInit;
    private IntPtr _stream;

    // One sample is one byte (8-bit mono), so byte counts are sample counts.
    private readonly int _startCushion;   // queued before playback begins (~60 ms)
    private readonly int _cap;            // most ever queued (~250 ms): the latency bound

    // Health counters, reset each Stats() read (diagnostics for choppy audio).
    private int _underruns, _drops;
    private long _fed;
    private bool _playing;

    public WaveAudio(int sampleRate)
    {
        _rate = sampleRate > 0 ? sampleRate : 22254;
        _startCushion = _rate * 60 / 1000;
        _cap = _rate / 4;
        try
        {
            SDL_SetAppMetadata("OpenMac", "0.1.0", "io.github.codingncaffeine.OpenMac");
            _sdlInit = SDL_InitSubSystem(SDL_INIT_AUDIO);
            if (!_sdlInit)
            {
                Log.Line("audio: SDL audio init failed -- " + LastError());
                return;
            }
            var spec = new SDL_AudioSpec { format = SDL_AUDIO_U8, channels = 1, freq = _rate };
            _stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, in spec, IntPtr.Zero, IntPtr.Zero);
            if (_stream == IntPtr.Zero)
                Log.Line("audio: no playback stream -- " + LastError());
        }
        catch (Exception ex) when (ex is DllNotFoundException or EntryPointNotFoundException)
        {
            // No SDL3 on this system: stay silent, never throw.
            Log.Line("audio: SDL3 unavailable -- " + ex.Message);
            _stream = IntPtr.Zero;
        }
    }

    public bool Ok => _stream != IntPtr.Zero;

    /// <summary>Queue this frame's samples for the device.</summary>
    public void Feed(byte[] samples, int count)
    {
        if (_stream == IntPtr.Zero || count <= 0) return;

        int queued = SDL_GetAudioStreamQueued(_stream);
        if (_playing && queued == 0) _underruns++;   // the device had run dry

        int room = _cap - queued;
        if (room <= 0) { _drops += count; return; }
        if (count > room) { _drops += count - room; count = room; }

        SDL_PutAudioStreamData(_stream, samples, count);
        _fed += count;

        if (!_playing && queued + count >= _startCushion)
        {
            SDL_ResumeAudioStreamDevice(_stream);   // streams open paused
            _playing = true;
        }
    }

    /// <summary>One-line health snapshot; resets the per-interval counters.</summary>
    public string Stats()
    {
        int queued = _stream != IntPtr.Zero ? SDL_GetAudioStreamQueued(_stream) : 0;
        string s = $"audio: queued={queued}/{_cap} fed={_fed} underruns={_underruns} drops={_drops}";
        _fed = 0; _underruns = 0; _drops = 0;
        return s;
    }

    private static string LastError() => Marshal.PtrToStringUTF8(SDL_GetError()) ?? "unknown error";

    public void Dispose()
    {
        if (_stream != IntPtr.Zero)
        {
            SDL_DestroyAudioStream(_stream);
            _stream = IntPtr.Zero;
        }
        if (_sdlInit) SDL_QuitSubSystem(SDL_INIT_AUDIO);
    }
}
