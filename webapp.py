#!/usr/bin/env python3
"""Веб-сервис DnD Soundboard: просмотр банков звуков и раскладки.

Работает отдельным процессом рядом с soundboard.py и не трогает железо:
читает keymap.py и папку sounds/ с диска. keymap.py перечитывается
автоматически, когда файл меняется, — перезапуск не нужен.

Запуск:   uv run webapp.py                  (порт 80, все интерфейсы)
          uv run webapp.py --port 8080      (например, для проверки на ПК)
"""

import argparse
import importlib.util
import os
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from layout import (  # noqa: E402
    COLS, ENCODER_FUNCTIONS, KEYMAP_FILE, ROWS, SOUNDS_DIR, SPECIAL_KEY_INFO,
    key_file, keymap_warnings, pretty_name,
)

WEB_DIR = BASE_DIR / "web"
AUDIO_EXTS = {".ogg", ".wav", ".mp3", ".flac"}
DEFAULT_PORT = int(os.environ.get("DNDBOARD_WEB_PORT", "80"))

# --- Чтение keymap.py ------------------------------------------------------
_keymap_lock = threading.Lock()
_keymap_cache = {"mtime": None, "banks": None, "bg": None}


def load_keymap():
    """Возвращает (BANKS, BG_TRACKS, mtime). Перечитывает файл, только если он изменился."""
    try:
        mtime = KEYMAP_FILE.stat().st_mtime
    except FileNotFoundError:
        raise HTTPException(500, f"{KEYMAP_FILE.name} not found")
    with _keymap_lock:
        if _keymap_cache["mtime"] != mtime:
            spec = importlib.util.spec_from_file_location("_keymap_live", KEYMAP_FILE)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:  # синтаксическая ошибка в процессе редактирования и т.п.
                raise HTTPException(500, f"Error in {KEYMAP_FILE.name}: {e}")
            _keymap_cache.update(mtime=mtime, banks=module.BANKS,
                                 bg=list(getattr(module, "BG_TRACKS", [])))
        return _keymap_cache["banks"], _keymap_cache["bg"], mtime


def sound_exists(rel):
    return (SOUNDS_DIR / rel).is_file()


# --- Сборка данных ---------------------------------------------------------
def build_layout():
    banks, bg_tracks, mtime = load_keymap()
    layers = []
    for b, bank in enumerate(banks):
        grid = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                cell = {"r": r, "c": c}
                if (r, c) in SPECIAL_KEY_INFO:
                    fid, label, descr = SPECIAL_KEY_INFO[(r, c)]
                    cell.update(type="function", function=fid, label=label, description=descr)
                else:
                    f = key_file(banks, b, r, c)
                    if f:
                        cell.update(type="sound", file=f, label=pretty_name(f),
                                    folder=Path(f).parts[0] if len(Path(f).parts) > 1 else "",
                                    missing=not sound_exists(f))
                    else:
                        cell.update(type="empty")
                row.append(cell)
            grid.append(row)
        layers.append({"index": b, "name": bank.get("name", f"Bank {b + 1}"), "keys": grid})

    return {
        "rows": ROWS,
        "cols": COLS,
        "layers": layers,
        "bg_tracks": [{"file": t, "label": pretty_name(t), "missing": not sound_exists(t)}
                      for t in bg_tracks],
        "encoder": [{"action": a, "description": d} for a, d in ENCODER_FUNCTIONS],
        "warnings": keymap_warnings(banks),
        "keymap_mtime": mtime,
    }


def build_sounds():
    """Банки звуков на устройстве = подпапки sounds/. Для каждого файла — где он используется."""
    banks, bg_tracks, _ = load_keymap()
    usage = {}
    for b, bank in enumerate(banks):
        for r in range(ROWS):
            for c in range(COLS):
                f = key_file(banks, b, r, c)
                if f:
                    usage.setdefault(f, []).append(
                        {"layer": b, "layer_name": bank.get("name", f"Bank {b + 1}"), "r": r, "c": c})
    bg_set = set(bg_tracks)

    folders = []
    if SOUNDS_DIR.is_dir():
        groups = {}
        for p in sorted(SOUNDS_DIR.rglob("*")):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                rel = p.relative_to(SOUNDS_DIR).as_posix()
                folder = rel.split("/")[0] if "/" in rel else ""
                groups.setdefault(folder, []).append({
                    "file": rel,
                    "label": pretty_name(rel),
                    "size": p.stat().st_size,
                    "used_on": usage.get(rel, []),
                    "background": rel in bg_set,
                })
        for name, tracks in sorted(groups.items()):
            folders.append({
                "name": name or "(root)",
                "tracks": tracks,
                "size": sum(t["size"] for t in tracks),
                "assigned": sum(1 for t in tracks if t["used_on"] or t["background"]),
            })

    return {
        "sounds_dir": str(SOUNDS_DIR),
        "found": SOUNDS_DIR.is_dir(),
        "banks": folders,
        "total_tracks": sum(len(f["tracks"]) for f in folders),
    }


# --- HTTP ------------------------------------------------------------------
app = FastAPI(title="DnD Soundboard", docs_url="/api/docs", redoc_url=None)


@app.get("/api/layout")
def api_layout():
    return build_layout()


@app.get("/api/sounds")
def api_sounds():
    return build_sounds()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


def main():
    ap = argparse.ArgumentParser(description="DnD Soundboard web UI")
    ap.add_argument("--host", default=os.environ.get("DNDBOARD_WEB_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args()
    # Проверяем порт заранее, чтобы выдать понятное сообщение вместо трейсбэка uvicorn
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((args.host, args.port))
    except PermissionError:
        sys.exit(f"Нет прав открыть порт {args.port}. Порты ниже 1024 требуют настройки — "
                 "см. README, раздел «Web UI». Или запустите с --port 8080.")
    except OSError as e:
        sys.exit(f"Порт {args.port} недоступен: {e}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
