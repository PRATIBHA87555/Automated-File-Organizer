"""Core logic for the File Organizer (no UI code here, so it is easy to test)."""
import json
import shutil
import time
from collections import namedtuple
from pathlib import Path

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tiff", ".ico", ".raw"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".epub"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods", ".tsv"},
    "Presentations": {".ppt", ".pptx", ".odp", ".key"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".go", ".rs",
             ".json", ".xml", ".yml", ".yaml", ".sh", ".sql", ".php", ".ipynb"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".apk", ".iso"},
}
EXT_MAP = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts}

# Files that are still downloading or are system junk are never touched.
IGNORE_SUFFIXES = {".tmp", ".crdownload", ".part", ".partial", ".download"}
IGNORE_NAMES = {"desktop.ini", "thumbs.db"}
HISTORY_FILE = ".organizer_history.json"
MAX_HISTORY = 20

Move = namedtuple("Move", "src dest category")


def category_for(path):
    return EXT_MAP.get(Path(path).suffix.lower(), "Others")


def _unique(dest, reserved=()):
    """Return a path that does not exist yet: file.txt -> file (1).txt -> file (2).txt"""
    dest = Path(dest)
    candidate, n = dest, 1
    while candidate.exists() or candidate in reserved:
        candidate = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
        n += 1
    return candidate


def scan(folder, min_age=2.0):
    """Top-level files in `folder` that are safe to move."""
    now = time.time()
    found = []
    for p in Path(folder).iterdir():
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.name.lower() in IGNORE_NAMES or p.suffix.lower() in IGNORE_SUFFIXES:
            continue
        try:
            if now - p.stat().st_mtime < min_age:  # probably still being written
                continue
        except OSError:
            continue
        found.append(p)
    return sorted(found)


def plan(folder, min_age=2.0):
    """Work out what would be moved where, without touching anything."""
    folder = Path(folder)
    moves, reserved = [], set()
    for src in scan(folder, min_age):
        cat = category_for(src)
        dest = _unique(folder / cat / src.name, reserved)
        reserved.add(dest)
        moves.append(Move(src, dest, cat))
    return moves


def _load_history(folder):
    path = Path(folder) / HISTORY_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_history(folder, history):
    path = Path(folder) / HISTORY_FILE
    path.write_text(json.dumps(history[-MAX_HISTORY:], indent=2), encoding="utf-8")


def apply(folder, moves, progress=None):
    """Perform the moves, record them for undo, return the list that succeeded."""
    done = []
    total = len(moves)
    for i, m in enumerate(moves, 1):
        try:
            m.dest.parent.mkdir(exist_ok=True)
            shutil.move(str(m.src), str(m.dest))
            done.append(m)
        except (OSError, shutil.Error):
            pass  # locked / permission problem: skip this file, keep going
        if progress:
            progress(i, total)
    if done:
        history = _load_history(folder)
        history.append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "moves": [{"from": str(m.src), "to": str(m.dest)} for m in done],
        })
        _save_history(folder, history)
    return done


def undo_last(folder, progress=None):
    """Reverse the most recent batch. Returns the number of files restored."""
    history = _load_history(folder)
    if not history:
        return 0
    batch = history.pop()
    items = batch["moves"]
    restored = 0
    for i, item in enumerate(reversed(items), 1):
        src, dest = Path(item["to"]), Path(item["from"])
        if src.exists():
            try:
                shutil.move(str(src), str(_unique(dest)))
                restored += 1
            except (OSError, shutil.Error):
                pass
        if progress:
            progress(i, len(items))
    # tidy up category folders that are now empty
    for item in items:
        parent = Path(item["to"]).parent
        try:
            parent.rmdir()
        except OSError:
            pass
    _save_history(folder, history)
    return restored
