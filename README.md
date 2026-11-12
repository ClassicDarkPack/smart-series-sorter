# Smart Series Sorter 📺

A local, dependency-free Python CLI that organizes TV-series episodes into season folders without modifying movie files.

یک ابزار خط فرمان پایتون برای مرتب‌سازی قسمت‌های سریال در آرشیوهای ترکیبی فیلم و سریال؛ با پیش‌نمایش امن، تطبیق پوشه‌ها و امکان بازگردانی جابه‌جایی‌ها.

## Features / ویژگی‌ها

- Recursively scan the selected library folder and subfolders.
- Detect common episode formats such as `S01E02`, `S1E2`, and `1x02`.
- Move episodes into `<Series>/Season NN/` while retaining original filenames.
- Prefer existing series directories using conservative name matching, including a unique year-suffixed match (e.g., `Dark Matter 2024`).
- Move matching sidecar files such as subtitles (`.srt`, `.ass`, `.vtt`) with episodes.
- Prevent overwrites by allocating unique video destinations; report sidecar conflicts.
- Preview changes by default (dry run); make changes only with `--apply`.
- Record completed moves in a JSON journal that can be used with `--undo`.
- No network access, metadata APIs, or third-party Python packages required.

> [!CAUTION]
> Back up important media before running `--apply`. Automatic identification uses filenames and may not recognize episodes without season/episode tags. Review the dry-run output first. Undo is best effort, not an atomic transaction; it skips paths that are missing or already occupied.

## Requirements

- Python 3.9 or newer (standard library only)
- Windows, Linux, or macOS

## Quick start / شروع سریع

Copy `smart_series_sorter.py` into your media library, for example `F:\film`.

**Preview (no changes):**

```powershell
python smart_series_sorter.py
```

**Apply changes:**

```powershell
python smart_series_sorter.py --apply
```

**Use a different root directory:**

```powershell
python smart_series_sorter.py --root "F:\film"
python smart_series_sorter.py --root "F:\film" --apply
```

**Undo a previous run** using its generated journal:

```powershell
python smart_series_sorter.py --undo "F:\film\.series_sorter_undo_YYYYMMDD_HHMMSS_microseconds.json"
```

The timestamp in this example is a placeholder: use the **actual** journal filename printed after your run.

## Example

Before:

```text
F:\film\
├── House Of Cards\
├── Dark Matter 2024\
├── House.of.Cards.S01E01.720p.mkv
├── Dark.Matter.S02E06.720p.mkv
├── MobLand.S02E01.mkv
└── American.Sniper.2014.mkv
```

After `--apply`:

```text
F:\film\
├── House Of Cards\
│   └── Season 01\
│       └── House.of.Cards.S01E01.720p.mkv
├── Dark Matter 2024\
│   └── Season 02\
│       └── Dark.Matter.S02E06.720p.mkv
├── MobLand\
│   └── Season 02\
│       └── MobLand.S02E01.mkv
└── American.Sniper.2014.mkv
```

Movies without episode tags remain in place. The tool also processes episodes directly inside existing series folders.

## How matching works

1. Parse an episode tag from the video filename.
2. Search existing top-level series directories, preferring exact title matches.
3. Try unique matches against directory names with year suffixes removed.
4. Use a conservative fuzzy match only for sufficiently close, unambiguous names.
5. Otherwise create a new series directory during the apply step.

Some similarly named shows or unusual folder layouts may need manual review. This tool **does not** use external TV databases to resolve show identity.

## Limitations / محدودیت‌ها

- Files without recognizable season/episode tags are not automatically sorted.
- Episode numbers are detected for identification but not used to rename files.
- The tool does not remove duplicate media, empty folders, or movie files.
- It does not identify shows by video content or read embedded metadata.
- An existing file in a destination folder may cause a numeric suffix to be added to an incoming video filename.
- Sidecar discovery is based on the video filename stem and common language suffixes.
- Undo does not remove any directories created during sorting and does not undo edits made after the sort.

## Safety / ایمنی

- Dry run is the default.
- No files are deleted or overwritten deliberately.
- Symlink files are excluded during scanning.
- Each completed move is recorded for best-effort reversal.
- Do not run another organizer simultaneously on the same library.

## License

MIT — see [LICENSE](LICENSE).