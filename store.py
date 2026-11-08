"""Хранение раскладки в SQLite (стандартная библиотека, без зависимостей).

Файл базы: dndboard.db рядом с проектом (можно переопределить переменной DNDBOARD_DB).
При первом запуске база заполняется из keymap.py — дальше keymap.py не читается,
раскладка меняется через веб-интерфейс.

Каждое сохранение увеличивает revision: веб по нему ловит конфликт, если раскладку
успели поменять из другой вкладки/браузера.
"""

import importlib.util
import os
import sqlite3
import time
from pathlib import Path

from layout import BASE_DIR, COLS, KEYMAP_FILE, ROWS, empty_grid, layers_from_keymap

DB_PATH = Path(os.environ.get("DNDBOARD_DB", BASE_DIR / "dndboard.db"))
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS layers (
    id       INTEGER PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    name     TEXT NOT NULL
);
-- Пустые клавиши не хранятся
CREATE TABLE IF NOT EXISTS keys (
    layer_id INTEGER NOT NULL REFERENCES layers(id) ON DELETE CASCADE,
    row      INTEGER NOT NULL,
    col      INTEGER NOT NULL,
    action   TEXT NOT NULL CHECK (action IN ('sound', 'function')),
    value    TEXT NOT NULL,     -- путь к файлу или id функции
    PRIMARY KEY (layer_id, row, col)
);
CREATE TABLE IF NOT EXISTS bg_tracks (
    position INTEGER PRIMARY KEY,
    file     TEXT NOT NULL
);
"""


class ConflictError(Exception):
    """Раскладку уже изменили после того, как её загрузил клиент."""


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)  # транзакции — вручную
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _read_keymap():
    spec = importlib.util.spec_from_file_location("_keymap_seed", KEYMAP_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return layers_from_keymap(module.BANKS), list(getattr(module, "BG_TRACKS", []))


def _meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def _set_meta(conn, key, value):
    conn.execute("INSERT INTO meta(key, value) VALUES(?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))


def _write_layers(conn, layers):
    conn.execute("DELETE FROM keys")
    conn.execute("DELETE FROM layers")
    for pos, layer in enumerate(layers):
        layer_id = conn.execute("INSERT INTO layers(position, name) VALUES(?, ?)",
                                (pos, layer["name"])).lastrowid
        rows = []
        for r in range(ROWS):
            for c in range(COLS):
                cell = layer["keys"][r][c]
                if cell:
                    value = cell["file"] if cell["type"] == "sound" else cell["function"]
                    rows.append((layer_id, r, c, cell["type"], value))
        conn.executemany("INSERT INTO keys(layer_id, row, col, action, value) VALUES(?,?,?,?,?)", rows)


def init_db():
    """Создаёт таблицы; если раскладки ещё нет — импортирует keymap.py.
    Безопасно при одновременном старте обоих сервисов (BEGIN IMMEDIATE)."""
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _meta(conn, "revision") is None:
                layers, bg = _read_keymap() if KEYMAP_FILE.exists() else ([], [])
                if not layers:
                    layers = [{"name": "Bank 1", "keys": empty_grid()}]
                _write_layers(conn, layers)
                conn.executemany("INSERT INTO bg_tracks(position, file) VALUES(?, ?)",
                                 list(enumerate(bg)))
                _set_meta(conn, "schema_version", SCHEMA_VERSION)
                _set_meta(conn, "revision", 1)
                _set_meta(conn, "updated_at", time.time())
                _set_meta(conn, "source", "imported from keymap.py")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def load():
    """Возвращает {"revision", "updated_at", "layers", "bg_tracks"}."""
    init_db()
    conn = _connect()
    try:
        conn.execute("BEGIN")   # одно согласованное чтение
        layers, by_id = [], {}
        for layer_id, name in conn.execute("SELECT id, name FROM layers ORDER BY position"):
            layer = {"name": name, "keys": empty_grid()}
            layers.append(layer)
            by_id[layer_id] = layer
        for layer_id, r, c, action, value in conn.execute(
                "SELECT layer_id, row, col, action, value FROM keys"):
            if layer_id in by_id and 0 <= r < ROWS and 0 <= c < COLS:
                key = "file" if action == "sound" else "function"
                by_id[layer_id]["keys"][r][c] = {"type": action, key: value}
        bg = [f for (f,) in conn.execute("SELECT file FROM bg_tracks ORDER BY position")]
        result = {
            "revision": int(_meta(conn, "revision", 0)),
            "updated_at": float(_meta(conn, "updated_at", 0)),
            "layers": layers,
            "bg_tracks": bg,
        }
        conn.execute("COMMIT")
        return result
    finally:
        conn.close()


def save_layers(layers, expected_revision):
    """Сохраняет раскладку (уже проверенную validate_layers). Возвращает новую revision.
    Бросает ConflictError, если в базе уже не expected_revision."""
    init_db()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = int(_meta(conn, "revision", 0))
            if expected_revision is not None and int(expected_revision) != current:
                raise ConflictError(current)
            _write_layers(conn, layers)
            _set_meta(conn, "revision", current + 1)
            _set_meta(conn, "updated_at", time.time())
            _set_meta(conn, "source", "web")
            conn.execute("COMMIT")
            return current + 1
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
