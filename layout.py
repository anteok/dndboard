"""Общая логика раскладки — без железа и без pygame.

Используется и сервисом клавиатуры (soundboard.py), и веб-сервисом (webapp.py),
поэтому здесь нельзя импортировать gpiozero / pygame / smbus2.

Раскладка в памяти:
    layers = [{"name": "Combat", "keys": grid}, ...]
    grid   = ROWS списков по COLS ячеек
    ячейка = None                                    — пустая клавиша
           | {"type": "sound", "file": "fight/x.ogg"} — звук (путь относительно sounds/)
           | {"type": "function", "function": "bank_next"} — функция плеера
"""

from pathlib import Path, PurePosixPath

BASE_DIR = Path(__file__).resolve().parent
SOUNDS_DIR = BASE_DIR / "sounds"
KEYMAP_FILE = BASE_DIR / "keymap.py"
AUDIO_EXTS = {".ogg", ".wav", ".mp3", ".flac"}

# Размер матрицы. Пины GPIO — в soundboard.py, их количество должно совпадать.
ROWS, COLS = 6, 14

# Функции плеера, которые можно повесить на любую клавишу: id -> (подпись, описание)
FUNCTIONS = {
    "bank_next": ("Next bank", "Switch to the next layer (cycles)"),
    "bg_prev":   ("BG prev", "Previous background track (starts playback)"),
    "bg_next":   ("BG next", "Next background track (starts playback)"),
    "bg_stop":   ("BG stop", "Stop background music"),
}

# Где функции стояли в старой раскладке (keymap.py). Нужно только для первого
# импорта keymap.py в базу — дальше раскладка меняется через веб.
DEFAULT_FUNCTION_KEYS = {
    (0, 0): "bank_next",
    (ROWS - 1, 0): "bg_prev",
    (ROWS - 1, 1): "bg_next",
    (ROWS - 1, 2): "bg_stop",
}

# Функции энкодера — не клавиши матрицы, но показываем их в вебе как легенду.
ENCODER_FUNCTIONS = [
    ("Rotate", "Volume (also unmutes)"),
    ("Short press", "Pause / resume background"),
    ("Hold 1 s", "Mute / unmute"),
]

MAX_LAYERS = 32
MAX_NAME_LEN = 40


def pretty_name(path):
    """'fight/sword_clash_01.ogg' -> 'Sword Clash 01'; '01_beginning_into...' -> 'Beginning Into...'"""
    stem = Path(path).stem
    parts = stem.split("_")
    if len(parts) > 1 and parts[0].isdigit():
        parts = parts[1:]
    return " ".join(p.capitalize() for p in parts)


def safe_sound_path(rel):
    """True, если rel — относительный путь к аудиофайлу внутри sounds/ (без '..' и т.п.)."""
    if not isinstance(rel, str) or not rel or "\\" in rel:
        return False
    p = PurePosixPath(rel)
    return (not p.is_absolute() and ".." not in p.parts
            and p.suffix.lower() in AUDIO_EXTS)


def empty_grid():
    return [[None] * COLS for _ in range(ROWS)]


def layers_from_keymap(banks):
    """Старый формат keymap.py (BANKS) -> layers. Служебные клавиши ставятся на прежние места."""
    layers = []
    for b_idx, bank in enumerate(banks):
        grid = empty_grid()
        keys = bank.get("keys", [])
        for r in range(ROWS):
            for c in range(COLS):
                if (r, c) in DEFAULT_FUNCTION_KEYS:
                    grid[r][c] = {"type": "function", "function": DEFAULT_FUNCTION_KEYS[(r, c)]}
                elif r < len(keys) and c < len(keys[r]) and keys[r][c]:
                    grid[r][c] = {"type": "sound", "file": keys[r][c]}
        layers.append({"name": bank.get("name") or f"Bank {b_idx + 1}", "keys": grid})
    return layers


def normalize_cell(cell):
    """Приводит ячейку из JSON к каноническому виду. Бросает ValueError на мусор."""
    if cell is None:
        return None
    if not isinstance(cell, dict):
        raise ValueError("cell must be an object or null")
    t = cell.get("type")
    if t in (None, "empty"):
        return None
    if t == "sound":
        f = cell.get("file")
        if not safe_sound_path(f):
            raise ValueError(f"bad sound path: {f!r}")
        return {"type": "sound", "file": f}
    if t == "function":
        fn = cell.get("function")
        if fn not in FUNCTIONS:
            raise ValueError(f"unknown function: {fn!r}")
        return {"type": "function", "function": fn}
    raise ValueError(f"unknown key type: {t!r}")


def validate_layers(raw_layers):
    """Проверяет раскладку, пришедшую из веба.

    Возвращает (layers, errors, warnings). Если errors не пуст — сохранять нельзя.
    """
    errors, warnings = [], []
    if not isinstance(raw_layers, list) or not raw_layers:
        return [], ["Layout must have at least one layer"], []
    if len(raw_layers) > MAX_LAYERS:
        return [], [f"Too many layers (max {MAX_LAYERS})"], []

    layers = []
    for i, raw in enumerate(raw_layers):
        where = f"Layer {i + 1}"
        if not isinstance(raw, dict):
            errors.append(f"{where}: must be an object")
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            errors.append(f"{where}: name is empty")
        elif len(name) > MAX_NAME_LEN:
            errors.append(f"{where}: name longer than {MAX_NAME_LEN} characters")
        where = f"Layer {i + 1} ({name})"

        keys = raw.get("keys")
        if not isinstance(keys, list) or len(keys) != ROWS or \
                any(not isinstance(row, list) or len(row) != COLS for row in keys):
            errors.append(f"{where}: key grid must be {ROWS}x{COLS}")
            continue
        grid = empty_grid()
        for r in range(ROWS):
            for c in range(COLS):
                try:
                    grid[r][c] = normalize_cell(keys[r][c])
                except ValueError as e:
                    errors.append(f"{where} [{r}][{c}]: {e}")
        layers.append({"name": name, "keys": grid})

        functions = {cell["function"] for row in grid for cell in row
                     if cell and cell["type"] == "function"}
        if len(raw_layers) > 1 and "bank_next" not in functions:
            errors.append(f"{where}: needs a 'Next bank' key, otherwise you can't leave this layer")
        missing = sorted({cell["file"] for row in grid for cell in row
                          if cell and cell["type"] == "sound"
                          and not (SOUNDS_DIR / cell["file"]).is_file()})
        for f in missing:
            warnings.append(f"{where}: file not found: {f}")
    return layers, errors, warnings


def sound_files(layers):
    """Все звуковые файлы, назначенные на клавиши."""
    return sorted({cell["file"] for layer in layers for row in layer["keys"]
                   for cell in row if cell and cell["type"] == "sound"})
