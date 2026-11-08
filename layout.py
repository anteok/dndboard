"""Общая логика раскладки — без железа и без pygame.

Используется и сервисом клавиатуры (soundboard.py), и веб-сервисом (webapp.py),
поэтому здесь нельзя импортировать gpiozero / pygame / smbus2.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SOUNDS_DIR = BASE_DIR / "sounds"
KEYMAP_FILE = BASE_DIR / "keymap.py"

# Размер матрицы. Пины GPIO — в soundboard.py, их количество должно совпадать.
ROWS, COLS = 6, 14

# Служебные клавиши: работают одинаково во всех банках.
KEY_BANK = (0, 0)
KEY_BG_PREV = (ROWS - 1, 0)   # нижний левый угол
KEY_BG_NEXT = (ROWS - 1, 1)
KEY_BG_STOP = (ROWS - 1, 2)

# (r, c) -> (id функции, короткая подпись, описание для веба)
SPECIAL_KEY_INFO = {
    KEY_BANK:    ("bank_next", "Next bank", "Switch to the next layer (cycles)"),
    KEY_BG_PREV: ("bg_prev", "BG prev", "Previous background track (starts playback)"),
    KEY_BG_NEXT: ("bg_next", "BG next", "Next background track (starts playback)"),
    KEY_BG_STOP: ("bg_stop", "BG stop", "Stop background music"),
}
SPECIAL_KEYS = set(SPECIAL_KEY_INFO)

# Функции энкодера — не клавиши матрицы, но показываем их в вебе как легенду.
ENCODER_FUNCTIONS = [
    ("Rotate", "Volume (also unmutes)"),
    ("Short press", "Pause / resume background"),
    ("Hold 1 s", "Mute / unmute"),
]


def pretty_name(path):
    """'fight/sword_clash_01.ogg' -> 'Sword Clash 01'; '01_beginning_into...' -> 'Beginning Into...'"""
    stem = Path(path).stem
    parts = stem.split("_")
    if len(parts) > 1 and parts[0].isdigit():
        parts = parts[1:]
    return " ".join(p.capitalize() for p in parts)


def key_file(banks, bank, r, c):
    """Файл на клавише (r, c) банка bank, или None (пусто / служебная / вне сетки)."""
    keys = banks[bank]["keys"]
    if r < len(keys) and c < len(keys[r]) and (r, c) not in SPECIAL_KEYS:
        return keys[r][c]
    return None


def keymap_warnings(banks):
    """Список предупреждений о несовпадении размера банков с матрицей."""
    out = []
    for b_idx, bank in enumerate(banks):
        keys = bank["keys"]
        if len(keys) != ROWS or any(len(row) != COLS for row in keys):
            shape = f"{len(keys)}x{max((len(r) for r in keys), default=0)}"
            out.append(f"Банк {b_idx + 1} ({bank['name']}) имеет размер {shape}, "
                       f"а матрица {ROWS}x{COLS}. Лишние клавиши игнорируются, недостающие пустые.")
    return out
