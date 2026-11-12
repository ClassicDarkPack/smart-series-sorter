#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smart Series Sorter v2 - safe, local-only, non-destructive series organizer.

Preview: python smart_series_sorter_v2.py
Apply:   python smart_series_sorter_v2.py --apply
Undo:    python smart_series_sorter_v2.py --undo "F:\\film\\.series_sorter_undo_....json"
Override archive root: --root "F:\\film"

No metadata APIs and no movie sorting: a recognizable episode tag is required.
"""
import argparse
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

VIDEO_EXTS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.m4v', '.ts', '.mpg', '.mpeg'}
SIDE_EXTS = {'.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx', '.nfo', '.jpg', '.jpeg', '.png', '.webp'}
# Match S01E02, S1E2, 1x02. Require separators/start around episode markers.
EPISODE_RE = re.compile(
    r'(?i)(?<![a-z0-9])s(?P<s1>\d{1,2})[ ._-]*e(?P<e1>\d{1,3})'
    r'|(?<![a-z0-9])(?P<s2>\d{1,2})x(?P<e2>\d{1,3})'
)
SEASON_DIR_RE = re.compile(r'(?i)^(?:season[ ._-]*|s)(\d{1,2})$')
GENERIC_DIRS = {'newfolder', 'downloads', 'download', 'temp', 'tmp', 'backup', 'dwnldata', 'movies', 'films', 'film', 'series', 'tv', 'subtitles', 'subs'}
RELEASE_WORDS = re.compile(r'(?i)\b(?:720p|1080p|2160p|480p|x264|x265|h264|h265|hevc|bluray|webrip|webdl|hdrip|10bit|aac)\b')
YEAR_END = re.compile(r'\s+(?:19\d{2}|20\d{2})$')


def clean_name(value):
    value = re.sub(r'[._]+', ' ', value)
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', value)
    value = re.sub(r'\s+', ' ', value).strip(' .-_')
    return value


def key(value):
    return ''.join(c.casefold() for c in clean_name(value) if c.isalnum())


def yearless(value):
    return YEAR_END.sub('', clean_name(value)).strip()


def parse_episode(path):
    match = EPISODE_RE.search(path.stem)
    if not match:
        return None
    prefix = path.stem[:match.start()]
    title = clean_name(prefix)
    if not title or RELEASE_WORDS.fullmatch(title):
        return None
    season = int(match.group('s1') or match.group('s2'))
    return title, season


def series_dirs(root):
    return sorted((p for p in root.iterdir()
                   if p.is_dir() and not p.is_symlink()
                   and key(p.name) not in GENERIC_DIRS
                   and not SEASON_DIR_RE.fullmatch(p.name)), key=lambda p: p.name.casefold())


def pick_series_dir(root, title, candidates):
    """Use strict exact matches; only use fuzzy matching if uniquely convincing.

    Yearless matches allow 'Dark Matter' -> 'Dark Matter 2024' but never merge
    two ambiguous year/version variants. Fuzzy matches are intentionally conservative.
    """
    target = key(title)
    exact = [p for p in candidates if key(p.name) == target]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, 'چند پوشه با نام دقیق یکسان'
    stripped = [p for p in candidates if key(yearless(p.name)) == target]
    if len(stripped) == 1:
        return stripped[0], None
    if len(stripped) > 1:
        return None, 'چند نسخه/سال از این سریال وجود دارد'

    # Avoid merging short names, franchises, remakes, and similarly-named shows.
    if len(target) < 9:
        return root / title, None
    scored = sorted(((SequenceMatcher(None, target, key(yearless(p.name))).ratio(), p)
                     for p in candidates), key=lambda item: item[0], reverse=True)
    if scored and scored[0][0] >= .93 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= .08):
        return scored[0][1], None
    return root / title, None


def find_sidecars(video):
    """Match exact video stem or stem followed by a language/tag separator."""
    stem = video.stem.casefold()
    found = []
    for item in video.parent.iterdir():
        if item.is_symlink() or not item.is_file() or item.suffix.casefold() not in SIDE_EXTS:
            continue
        item_stem = item.stem.casefold()
        if item_stem == stem or (item_stem.startswith(stem) and
                                 len(item_stem) > len(stem) and item_stem[len(stem)] in '._- '):
            found.append(item)
    return sorted(found)


def unique_video_destination(dst, reserved, src):
    """Return same path for already-in-place, otherwise reserve unique name."""
    if dst == src:
        return dst
    n = 0
    candidate = dst
    while candidate in reserved or candidate.exists():
        n += 1
        candidate = dst.with_name(f'{dst.stem} ({n}){dst.suffix}')
    reserved.add(candidate)
    return candidate


def create_plan(root):
    # Snapshot first, so traversal does not see newly-created directories.
    videos = sorted((p for p in root.rglob('*') if p.is_file() and not p.is_symlink()
                     and p.suffix.casefold() in VIDEO_EXTS), key=lambda p: str(p).casefold())
    candidates = series_dirs(root)
    reserved = set()
    operations = []
    stats = Counter()
    notes = []
    for video in videos:
        result = parse_episode(video)
        if result is None:
            stats['not_episode'] += 1
            continue
        title, season = result
        folder, problem = pick_series_dir(root, title, candidates)
        if problem:
            stats['ambiguous'] += 1
            notes.append(f'[بررسی دستی] {video}: {problem}')
            continue
        # Create the target in the inventory for *subsequent* files in this plan.
        if folder not in candidates:
            candidates.append(folder)
        target_dir = folder / f'Season {season:02d}'
        target = unique_video_destination(target_dir / video.name, reserved, video)
        if target == video:
            stats['already_sorted'] += 1
            continue
        operations.append((video, target))
        stats['videos'] += 1
        for side in find_sidecars(video):
            if side in (src for src, _ in operations):
                continue
            suffix_after_stem = side.stem[len(video.stem):]
            proposed = target_dir / (target.stem + suffix_after_stem + side.suffix)
            # Sidecar conflicts are resolved without breaking its correspondence to video.
            if proposed.exists() or proposed in reserved:
                notes.append(f'[تداخل فایل جانبی؛ منتقل نشد] {side} -> {proposed}')
                stats['sidecar_conflicts'] += 1
                continue
            reserved.add(proposed)
            operations.append((side, proposed))
            stats['sidecars'] += 1
    return operations, stats, notes


def write_journal(path, root, moves):
    payload = {'root': str(root), 'moves': moves}
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def apply_plan(root, operations):
    journal = root / ('.series_sorter_undo_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    completed = []
    write_journal(journal, root, completed)
    errors = 0
    for src, dst in operations:
        try:
            if not src.is_file() or src.is_symlink() or dst.exists():
                raise RuntimeError('منبع پیدا نشد، symlink است یا مقصد اشغال شده')
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            completed.append({'from': str(src), 'to': str(dst)})
            write_journal(journal, root, completed)
            print(f'[OK] {src} -> {dst}')
        except Exception as exc:
            errors += 1
            print(f'[ERROR] {src}: {exc}', file=sys.stderr)
    print(f'\nمنتقل شد: {len(completed)} | خطا: {errors}\nگزارش بازگردانی: {journal}')


def undo(journal):
    with journal.open('r', encoding='utf-8') as f:
        data = json.load(f)
    moves = data.get('moves', [])
    undone = 0
    for entry in reversed(moves):
        src = Path(entry['to'])
        dst = Path(entry['from'])
        if not src.exists() or dst.exists():
            print(f'[SKIP] امکان بازگردانی امن نیست: {src} -> {dst}')
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        undone += 1
        print(f'[UNDO] {src} -> {dst}')
    print(f'بازگردانده شد: {undone}/{len(moves)}')
    # Keep journal for audit; reruns will skip already-undone moves.


def main():
    parser = argparse.ArgumentParser(description='مرتب‌ساز امن سریال‌ها (پیش‌فرض: فقط نمایش تغییرات)')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--apply', action='store_true', help='اجرای واقعی جابه‌جایی‌ها')
    parser.add_argument('--undo', type=Path, metavar='JOURNAL', help='بازگردانی انتقال‌های ثبت‌شده')
    args = parser.parse_args()
    if args.undo:
        undo(args.undo.resolve())
        return
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f'پوشه پیدا نشد: {root}')
    operations, stats, notes = create_plan(root)
    print(f'ریشه: {root}\nحالت: {"اجرا" if args.apply else "پیش‌نمایش (بدون تغییر)"}\n')
    for src, dst in operations:
        print(f'{src.relative_to(root)}  ->  {dst.relative_to(root)}')
    for note in notes:
        print(note)
    print(f'\nویدیو: {stats["videos"]} | فایل جانبی: {stats["sidecars"]} | '
          f'از قبل مرتب: {stats["already_sorted"]} | غیرقسمتی/فیلم: {stats["not_episode"]} | '
          f'مبهم: {stats["ambiguous"]} | تداخل جانبی: {stats["sidecar_conflicts"]}')
    if args.apply and operations:
        apply_plan(root, operations)
    elif not args.apply:
        print('برای انجام انتقال‌ها، دستور را با --apply اجرا کنید.')


if __name__ == '__main__':
    main()