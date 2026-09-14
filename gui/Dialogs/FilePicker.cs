using System.IO;
using Avalonia.Controls;
using Avalonia.Platform.Storage;

namespace OpenMac.Gui.Dialogs;

/// <summary>
/// File dialogs that come back to where you were last time you chose that kind
/// of file. ROMs, floppy images and hard-disk images live in different folders
/// and are picked weeks apart, so one shared "last folder" is worse than none —
/// it sends you to whichever you touched most recently.
///
/// <see cref="Settings"/> holds the folder last used for each purpose, and the
/// picker is started there. The dialogs themselves are the desktop's own (the
/// XDG portal on KDE and GNOME), reached through Avalonia's storage provider.
/// </summary>
internal static class FilePicker
{
    // Purposes are by kind of file, not by menu item: both floppy drives draw
    // from the same image library, and attaching a hard disk starts where the
    // last one was created.
    public const string Rom = "rom";
    public const string VideoRom = "video-rom";
    public const string Floppy = "floppy";
    public const string HardDisk = "harddisk";
    public const string Cd = "cd";
    public const string Folder = "folder";

    /// <summary>
    /// Ask for an existing file. Returns null if the user backed out; otherwise
    /// the chosen path, with its folder remembered for this purpose.
    /// </summary>
    public static string? Open(Window owner, Settings settings, string purpose,
                               string title, string filter, string? preselect = null)
    {
        IStorageProvider sp = owner.StorageProvider;
        var options = new FilePickerOpenOptions
        {
            Title = title,
            AllowMultiple = false,
            FileTypeFilter = ParseFilter(filter),
            SuggestedStartLocation = StartFolder(sp, settings, purpose, preselect),
        };
        if (!string.IsNullOrEmpty(preselect) && File.Exists(preselect))
            options.SuggestedFileName = Path.GetFileName(preselect);
        IReadOnlyList<IStorageFile> files = ModalLoop.Wait(sp.OpenFilePickerAsync(options));
        string? path = files.Count > 0 ? files[0].TryGetLocalPath() : null;
        if (path is null) return null;
        settings.RememberFolder(purpose, path);
        return path;
    }

    /// <summary>
    /// Ask where to write a new file. Returns null if the user backed out.
    /// </summary>
    public static string? Save(Window owner, Settings settings, string purpose,
                               string title, string filter, string suggestedName,
                               string defaultExt, string? fallback = null)
    {
        IStorageProvider sp = owner.StorageProvider;
        var options = new FilePickerSaveOptions
        {
            Title = title,
            FileTypeChoices = ParseFilter(filter),
            DefaultExtension = defaultExt.TrimStart('.'),
            SuggestedFileName = suggestedName,
            ShowOverwritePrompt = true,
            SuggestedStartLocation = StartFolder(sp, settings, purpose, null, fallback),
        };
        IStorageFile? file = ModalLoop.Wait(sp.SaveFilePickerAsync(options));
        string? path = file?.TryGetLocalPath();
        if (path is null) return null;
        settings.RememberFolder(purpose, path);
        return path;
    }

    /// <summary>Ask for a folder. Returns null if the user backed out.</summary>
    public static string? OpenFolder(Window owner, string title, string? initial)
    {
        IStorageProvider sp = owner.StorageProvider;
        var options = new FolderPickerOpenOptions { Title = title, AllowMultiple = false };
        if (!string.IsNullOrEmpty(initial) && Directory.Exists(initial))
            options.SuggestedStartLocation = ModalLoop.Wait(sp.TryGetFolderFromPathAsync(initial));
        IReadOnlyList<IStorageFolder> folders = ModalLoop.Wait(sp.OpenFolderPickerAsync(options));
        return folders.Count > 0 ? folders[0].TryGetLocalPath() : null;
    }

    // Start at the folder of the file used last if it is still there, otherwise
    // at the folder remembered for this purpose.
    //
    // `fallback` covers a profile with no folder history: an install that has
    // been opening the same ROM for weeks already knows where that ROM lives, so
    // there is no reason to start it at the home folder.
    private static IStorageFolder? StartFolder(IStorageProvider sp, Settings settings, string purpose,
                                               string? preselect, string? fallback = null)
    {
        string? dir = null;
        if (!string.IsNullOrEmpty(preselect) && File.Exists(preselect))
            dir = Path.GetDirectoryName(preselect);
        dir ??= settings.FolderFor(purpose);
        if (dir is null)
        {
            foreach (string? candidate in new[] { preselect, fallback })
            {
                if (string.IsNullOrEmpty(candidate)) continue;
                string? parent = Path.GetDirectoryName(candidate);
                if (!string.IsNullOrEmpty(parent) && Directory.Exists(parent)) { dir = parent; break; }
            }
        }
        return dir is null ? null : ModalLoop.Wait(sp.TryGetFolderFromPathAsync(dir));
    }

    // "Description (*.a;*.b)|*.a;*.b|All files (*.*)|*.*" -> picker file types.
    // Linux pickers match patterns case-sensitively, and period ROM and disk
    // dumps are as often named .ROM or .IMG as .rom or .img, so every pattern
    // also goes in upper case.
    private static List<FilePickerFileType> ParseFilter(string filter)
    {
        var types = new List<FilePickerFileType>();
        string[] parts = filter.Split('|');
        for (int i = 0; i + 1 < parts.Length; i += 2)
        {
            var patterns = new List<string>();
            foreach (string raw in parts[i + 1].Split(';', StringSplitOptions.RemoveEmptyEntries))
            {
                string p = raw.Trim() == "*.*" ? "*" : raw.Trim();
                if (!patterns.Contains(p)) patterns.Add(p);
                string upper = p.ToUpperInvariant();
                if (!patterns.Contains(upper)) patterns.Add(upper);
            }
            types.Add(new FilePickerFileType(parts[i]) { Patterns = patterns });
        }
        return types;
    }
}
