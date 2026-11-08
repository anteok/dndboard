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
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

# Загрузка звуков
MAX_UPLOAD_MB = int(os.environ.get("DNDBOARD_MAX_UPLOAD_MB", "100"))   # на один файл
MIN_FREE_MB = 100           # сколько места оставить на SD-карте после загрузки
MAX_SEGMENT_LEN = 60        # длина имени папки/файла


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


# --- Загрузка звуков -------------------------------------------------------
# LCD 1602 показывает только ASCII (в его ПЗУ нет кириллицы), а имя файла выводится
# на экран при нажатии клавиши, — поэтому имена транслитерируем в латиницу.
_TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяіїєґ",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r",
     "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya",
     "i", "yi", "ye", "g"]))


def clean_name(name, what):
    """'Dragon Roar (1)' -> 'dragon_roar_1', 'Гром' -> 'grom'. Только ASCII."""
    name = "".join(_TRANSLIT.get(ch, ch) for ch in name.strip().lower())
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()   # é -> e
    name = re.sub(r"[^a-z0-9_-]+", "_", name).strip("_-")
    name = re.sub(r"_+", "_", name)[:MAX_SEGMENT_LEN].strip("_-")
    if not name:
        raise HTTPException(400, f"Invalid {what} name")
    return name


def audio_kind(head):
    """Тип аудио по первым байтам файла (расширению не верим)."""
    if head[:4] == b"OggS":
        return ".ogg"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return ".wav"
    if head[:4] == b"fLaC":
        return ".flac"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return ".mp3"
    return None


@app.post("/api/sounds/upload")
def api_upload(file: UploadFile = File(...), folder: str = Form(...), overwrite: bool = Form(False)):
    """Загружает один звук в sounds/<folder>/. Папка создаётся, если её нет.

    Имя файла нормализуется (строчные буквы, '_' вместо пробелов и знаков).
    Существующий файл заменяется только при overwrite=true. Раскладку не меняет и
    soundboard не перезапускает: новый звук заиграет, когда его поставят на клавишу.
    """
    folder_name = clean_name(folder, "bank")
    src = Path(file.filename or "")
    ext = src.suffix.lower()
    if ext not in AUDIO_EXTS:
        raise HTTPException(415, f"{src.name}: only {', '.join(sorted(AUDIO_EXTS))} files are supported")
    target_rel = f"{folder_name}/{clean_name(src.stem, 'file')}{ext}"
    target = SOUNDS_DIR / target_rel

    head = file.file.read(16)
    kind = audio_kind(head)
    if kind != ext:
        raise HTTPException(415, f"{src.name}: doesn't look like a real {ext} file")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"{src.name}: larger than {MAX_UPLOAD_MB} MB")
    SOUNDS_DIR.mkdir(exist_ok=True)
    free = shutil.disk_usage(SOUNDS_DIR).free
    if free - size < MIN_FREE_MB * 1024 * 1024:
        raise HTTPException(507, f"Not enough free space on the device ({free // 1048576} MB free)")

    existed = target.exists()
    if existed and not overwrite:
        raise HTTPException(409, f"{target_rel} already exists")

    target.parent.mkdir(parents=True, exist_ok=True)
    # пишем во временный файл рядом и переименовываем — недокачанный файл не появится в банке
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".upload-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(file.file, out, 1024 * 1024)
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise

    return {
        "file": target_rel,
        "label": pretty_name(target_rel),
        "size": size,
        "replaced": existed,
        "renamed": src.name != target.name,
    }


# Звуковые файлы для прослушивания в браузере: /sounds/<банк>/<файл>.
# StaticFiles сам не выпускает за пределы папки и поддерживает перемотку (Range).
class SoundFiles(StaticFiles):
    async def get_response(self, path, scope):
        if Path(path).suffix.lower() not in AUDIO_EXTS:     # только аудио, без .part и прочего
            raise HTTPException(404)
        return await super().get_response(path, scope)


app.mount("/sounds", SoundFiles(directory=SOUNDS_DIR, check_dir=False), name="sounds")


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
