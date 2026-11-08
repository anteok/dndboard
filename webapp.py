#!/usr/bin/env python3
"""Веб-сервис DnD Soundboard: банки звуков и редактор раскладки.

Работает отдельным процессом рядом с soundboard.py и не трогает железо.
Раскладка хранится в SQLite (store.py). Кнопка Save в вебе сохраняет её
и перезапускает soundboard.py (команда — DNDBOARD_RESTART_CMD,
по умолчанию `systemctl --user restart dndboard`).

Запуск:   uv run webapp.py                  (порт 80, все интерфейсы)
          uv run webapp.py --port 8080      (например, для проверки на ПК)
"""

import argparse
import os
import shlex
import socket
import subprocess
import sys
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from layout import (  # noqa: E402
    AUDIO_EXTS, COLS, ENCODER_FUNCTIONS, FUNCTIONS, ROWS, SOUNDS_DIR,
    pretty_name, validate_layers,
)
import store  # noqa: E402

WEB_DIR = BASE_DIR / "web"
DEFAULT_PORT = int(os.environ.get("DNDBOARD_WEB_PORT", "80"))
RESTART_CMD = os.environ.get("DNDBOARD_RESTART_CMD", "systemctl --user restart dndboard")
RESTART_TIMEOUT = 30


def sound_exists(rel):
    return (SOUNDS_DIR / rel).is_file()


def folder_of(rel):
    parts = Path(rel).parts
    return parts[0] if len(parts) > 1 else ""


def load_layout():
    try:
        return store.load()
    except Exception as e:
        raise HTTPException(500, f"Can't read layout database {store.DB_PATH}: {e}")


# --- Сборка данных ---------------------------------------------------------
def describe_cell(cell, r, c):
    out = {"r": r, "c": c}
    if not cell:
        out["type"] = "empty"
    elif cell["type"] == "function":
        label, descr = FUNCTIONS.get(cell["function"], (cell["function"], "Unknown function"))
        out.update(type="function", function=cell["function"], label=label, description=descr)
    else:
        f = cell["file"]
        out.update(type="sound", file=f, label=pretty_name(f), folder=folder_of(f),
                   missing=not sound_exists(f))
    return out


def build_layout():
    data = load_layout()
    layers = [{
        "index": b,
        "name": layer["name"],
        "keys": [[describe_cell(layer["keys"][r][c], r, c) for c in range(COLS)] for r in range(ROWS)],
    } for b, layer in enumerate(data["layers"])]
    return {
        "rows": ROWS,
        "cols": COLS,
        "revision": data["revision"],
        "updated_at": data["updated_at"],
        "layers": layers,
        "functions": [{"id": k, "label": v[0], "description": v[1]} for k, v in FUNCTIONS.items()],
        "bg_tracks": [{"file": t, "label": pretty_name(t), "missing": not sound_exists(t)}
                      for t in data["bg_tracks"]],
        "encoder": [{"action": a, "description": d} for a, d in ENCODER_FUNCTIONS],
    }


def build_sounds():
    """Банки звуков на устройстве = подпапки sounds/. Для каждого файла — где он используется."""
    data = load_layout()
    usage = {}
    for b, layer in enumerate(data["layers"]):
        for r in range(ROWS):
            for c in range(COLS):
                cell = layer["keys"][r][c]
                if cell and cell["type"] == "sound":
                    usage.setdefault(cell["file"], []).append(
                        {"layer": b, "layer_name": layer["name"], "r": r, "c": c})
    bg_set = set(data["bg_tracks"])

    folders = []
    if SOUNDS_DIR.is_dir():
        groups = {}
        for p in sorted(SOUNDS_DIR.rglob("*")):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                rel = p.relative_to(SOUNDS_DIR).as_posix()
                groups.setdefault(folder_of(rel), []).append({
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
        "revision": data["revision"],
        "sounds_dir": str(SOUNDS_DIR),
        "found": SOUNDS_DIR.is_dir(),
        "banks": folders,
        "total_tracks": sum(len(f["tracks"]) for f in folders),
    }


def restart_soundboard():
    """Перезапускает сервис клавиатуры. Возвращает {"ok", "message"}."""
    if not RESTART_CMD.strip():
        return {"ok": False, "message": "Restart is disabled (DNDBOARD_RESTART_CMD is empty)"}
    try:
        res = subprocess.run(shlex.split(RESTART_CMD), capture_output=True, text=True,
                             timeout=RESTART_TIMEOUT)
    except FileNotFoundError:
        return {"ok": False, "message": f"Command not found: {RESTART_CMD}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": f"Restart took longer than {RESTART_TIMEOUT} s"}
    if res.returncode != 0:
        err = (res.stderr or res.stdout).strip() or f"exit code {res.returncode}"
        return {"ok": False, "message": f"Restart failed: {err}"}
    return {"ok": True, "message": "Soundboard restarted"}


# --- HTTP ------------------------------------------------------------------
app = FastAPI(title="DnD Soundboard", docs_url="/api/docs", redoc_url=None)


@app.get("/api/layout")
def api_layout():
    return build_layout()


@app.put("/api/layout")
def api_save_layout(body: dict = Body(...)):
    """Сохраняет раскладку целиком и перезапускает soundboard.py.

    Тело: {"revision": <из GET>, "layers": [{"name": ..., "keys": 6x14 ячеек}]}.
    Ячейка: {"type": "empty"} | {"type": "sound", "file": ...} | {"type": "function", "function": ...}.
    Лишние поля (label, missing, ...) из GET игнорируются.
    """
    layers, errors, warnings = validate_layers(body.get("layers"))
    if errors:
        raise HTTPException(422, {"errors": errors, "warnings": warnings})
    try:
        revision = store.save_layers(layers, body.get("revision"))
    except store.ConflictError as e:
        raise HTTPException(409, {"errors": [
            f"The layout was changed elsewhere (now revision {e.args[0]}). "
            "Reload the page to see it; your changes are not saved."]})
    return {"revision": revision, "warnings": warnings, "restart": restart_soundboard()}


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
