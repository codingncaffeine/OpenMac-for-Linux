using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using Avalonia.Threading;
using OpenMac.Gui.Dialogs;

namespace OpenMac.Gui;

public partial class App : Application
{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        Log.Init();
        Log.Line("app startup");

        Dispatcher.UIThread.UnhandledException += OnDispatcherUnhandled;
        AppDomain.CurrentDomain.UnhandledException += (_, ev) =>
            Log.Line("FATAL (AppDomain): " + ev.ExceptionObject);

        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.MainWindow = new MainWindow();
            desktop.Exit += (_, _) => Log.Line("app exit");
        }

        base.OnFrameworkInitializationCompleted();
    }

    private void OnDispatcherUnhandled(object? sender, DispatcherUnhandledExceptionEventArgs e)
    {
        Log.Line("UNHANDLED: " + e.Exception);
        MessageBox.Show(
            "An unexpected error occurred:\n\n" + e.Exception.Message + "\n\nDetails were written to:\n" + Log.Path,
            "OpenMac", MessageBoxButton.OK, MessageBoxImage.Error);
        e.Handled = true;   // keep the app alive if we can
    }
}
