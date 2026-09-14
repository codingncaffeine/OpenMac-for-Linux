using Avalonia;

namespace OpenMac.Gui;

internal static class Program
{
    // Nothing that touches Avalonia may run before BuildAvaloniaApp: the
    // platform is not initialised yet.
    [STAThread]
    public static void Main(string[] args) =>
        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);

    public static AppBuilder BuildAvaloniaApp() =>
        AppBuilder.Configure<App>()
            .UsePlatformDetect()
            .WithInterFont()
            .LogToTrace();
}
