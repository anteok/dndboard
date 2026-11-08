#!/usr/bin/env python3
"""DnD Soundboard для Raspberry Pi 3B.

Железо: матрица клавиш 6x14 с диодами, LCD 1602A по I2C, энкодер EC11 с кнопкой.

Управление: любая клавиша — звук или функция плеера (следующий банк,
фоновый трек назад / вперёд / стоп); что где — задаётся в раскладке.
  Энкодер: вращение — громкость, короткое нажатие — пауза/продолжить фон,
           удержание 1 с — Mute (вращение снимает Mute)

Раскладка хранится в SQLite (dndboard.db) и редактируется через веб (webapp.py).
При первом запуске база создаётся из keymap.py. Раскладка читается при старте:
кнопка Save в вебе сохраняет её и перезапускает этот сервис.
Запуск:   uv run soundboard.py
Раскладка: uv run soundboard.py --map   (печатает и выходит, работает и без железа)
Звуковые устройства: uv run soundboard.py --audio-devices
"""

import signal
import sys
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from layout import (  # noqa: E402
    SOUNDS_DIR, ROWS, COLS, FUNCTIONS, KEYMAP_FILE, pretty_name, sound_files, layers_from_keymap,
)
import store  # noqa: E402

# --- Настройки -------------------------------------------------------------
# Распределение GPIO (Pi 3B, всего 26 свободных: GPIO 2–27):
#   I2C дисплей: 2, 3      Энкодер: 20, 21 + кнопка 16
#   Матрица 6x14: 20 пинов (ниже)      Запасной: GPIO 8
# Перед запуском в raspi-config (Interface Options):
#   Serial Port -> login shell: No, hardware: No   (GPIO 14/15 заняты матрицей)
#   SPI -> Disable                                  (GPIO 7, 9, 10, 11 заняты матрицей)
#   I2C -> Enable
# Диоды: строки подтянуты к 3.3 В, активный столбец тянется к земле, ток идёт
# строка -> кнопка -> диод -> столбец. Анод к строке, катод (полоска) к столбцу.
ROW_PINS = [4, 17, 27, 22, 10, 25]
COL_PINS = [9, 11, 5, 6, 13, 19, 26, 14, 15, 18, 23, 24, 12, 7]
ENC_A, ENC_B, ENC_BTN = 20, 21, 16

# Размер матрицы задан в layout.py (его читает и веб-сервис)
assert (len(ROW_PINS), len(COL_PINS)) == (ROWS, COLS), "пины не совпадают с ROWS/COLS в layout.py"

VOLUME_STEP = 0.05
START_VOLUME = 0.7
MIXER_CHANNELS = 32       # сколько эффектов может звучать одновременно
AUDIO_BUFFER = 1024       # 512 на Pi 3 даёт щелчки/треск (недогрузка буфера). Трещит — ставьте 2048
# Запас по громкости: эффекты и музыка складываются, и без запаса сумма
# упирается в 0 dB и хрипит (клиппинг). Громкость энкодера умножается на эти коэффициенты.
SFX_GAIN = 0.8
MUSIC_GAIN = 0.55
# Звуковое устройство. None — системное по умолчанию (на Pi 3 это 3.5 мм джек).
# Для USB-звуковой карты впишите её имя из `uv run soundboard.py --audio-devices`.
AUDIO_DEVICE = None
TEMP_MSG_SECONDS = 1.5    # сколько держится временное сообщение на экране
RETRIGGER_GUARD = 0.06    # защита от дребезга: повторное срабатывание клавиши не раньше, сек
SCAN_SETTLE = 0.002       # пауза между столбцами при сканировании


def load_layout():
    """Раскладка из базы. Если база не открывается — аварийно берём keymap.py,
    чтобы доска всё равно играла."""
    try:
        data = store.load()
        return data["layers"], data["bg_tracks"]
    except Exception as e:
        print(f"Не удалось прочитать раскладку из {store.DB_PATH}: {e}. Беру {KEYMAP_FILE.name}.")
        from keymap import BANKS, BG_TRACKS
        return layers_from_keymap(BANKS), list(BG_TRACKS)


LAYERS, BG_TRACKS = load_layout()


def key_label(cell):
    if not cell:
        return "-"
    if cell["type"] == "function":
        return f"<< {FUNCTIONS[cell['function']][0].upper()} >>"
    return pretty_name(cell["file"])


def print_map():
    for b_idx, layer in enumerate(LAYERS):
        print(f"\n=== Банк {b_idx + 1}: {layer['name']} ===")
        for r in range(ROWS):
            for c in range(COLS):
                print(f"  [{r}][{c:>2}] {key_label(layer['keys'][r][c])}")
    print("\n=== Фоновые треки ===")
    for i, t in enumerate(BG_TRACKS):
        print(f"  {i + 1:>2}. {pretty_name(t)}")


if "--map" in sys.argv:
    print_map()
    sys.exit(0)

import pygame  # noqa: E402

if "--audio-devices" in sys.argv:
    from pygame._sdl2 import audio as sdl2_audio
    pygame.mixer.init()
    print("Устройства вывода звука (впишите имя в AUDIO_DEVICE):")
    for name in sdl2_audio.get_audio_device_names(False):
        print(f"  {name}")
    sys.exit(0)

from gpiozero import DigitalOutputDevice, Button, RotaryEncoder  # noqa: E402

try:
    from lcd1602 import LCD
except Exception:  # нет smbus2 — работаем без экрана
    LCD = None


# --- Дисплей ---------------------------------------------------------------
class Display:
    """Всё рисование на LCD идёт только из главного цикла через render().
    Колбэки энкодера (они работают в других потоках) лишь меняют состояние,
    поэтому две записи в I2C никогда не пересекутся."""

    def __init__(self):
        self.lcd = None
        if LCD is not None:
            try:
                self.lcd = LCD()
            except Exception as e:
                print(f"Дисплей не подключен или ошибка: {e}")
        self._shown = [None, None]

    def write(self, line1, line2):
        lines = [line1[:16].ljust(16), line2[:16].ljust(16)]
        if self.lcd:
            for i, text in enumerate(lines):
                if text != self._shown[i]:   # перерисовываем только изменившиеся строки
                    try:
                        self.lcd.text(text, i + 1)
                        self._shown[i] = text
                    except Exception as e:
                        print(f"Ошибка LCD: {e}")
        elif lines != self._shown:
            print(f"[LCD] {lines[0]} | {lines[1]}")
            self._shown = lines

    def clear(self):
        if self.lcd:
            try:
                self.lcd.clear()
            except Exception:
                pass


display = Display()
display.write("System Booting..", "Please wait...")

# --- Звук ------------------------------------------------------------------
# 44100 Гц совпадает с частотой всех файлов в sounds/ — без пересэмплирования
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER,
                      devicename=AUDIO_DEVICE)
try:
    pygame.mixer.init()
except pygame.error as e:
    if AUDIO_DEVICE is None:
        raise
    print(f"Устройство '{AUDIO_DEVICE}' не открылось ({e}), беру системное по умолчанию")
    pygame.mixer.quit()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER)
pygame.mixer.set_num_channels(MIXER_CHANNELS)


def load_banks():
    """Грузим в память только файлы из раскладки; повторяющийся файл — один раз."""
    cache = {}
    wanted = sound_files(LAYERS)
    total = len(wanted)
    for i, f in enumerate(wanted, 1):
        if i % 10 == 0 or i == total:
            display.write("Loading sounds", f"{i}/{total}")
        try:
            cache[f] = pygame.mixer.Sound(str(SOUNDS_DIR / f))
        except (pygame.error, FileNotFoundError, OSError) as e:
            print(f"Не загрузился {f}: {e}")
            cache[f] = None

    loaded = [
        [[cache.get(cell["file"]) if cell and cell["type"] == "sound" else None for cell in row]
         for row in layer["keys"]]
        for layer in LAYERS
    ]
    missing = sum(1 for s in cache.values() if s is None)
    if missing:
        print(f"Внимание: не найдено файлов: {missing}")
    return loaded, [s for s in cache.values() if s]


loaded_banks, all_sounds = load_banks()

# --- Состояние -------------------------------------------------------------
state_lock = threading.RLock()
current_bank = 0
volume = START_VOLUME
is_muted = False
bg_index = 0
bg_state = "stopped"          # stopped / playing / paused
temp_message = None
temp_until = 0.0
ui_dirty = True


def show_temp(msg):
    """Временное сообщение в первой строке экрана."""
    global temp_message, temp_until, ui_dirty
    with state_lock:
        temp_message = msg
        temp_until = time.monotonic() + TEMP_MSG_SECONDS
        ui_dirty = True


def apply_volume():
    v = 0.0 if is_muted else volume
    pygame.mixer.music.set_volume(v * MUSIC_GAIN)
    for s in all_sounds:
        s.set_volume(v * SFX_GAIN)


def render():
    """Рисует экран, если что-то поменялось. Вызывается только из главного цикла."""
    global temp_message, ui_dirty
    with state_lock:
        if temp_message and time.monotonic() > temp_until:
            temp_message = None
            ui_dirty = True
        if not ui_dirty:
            return
        ui_dirty = False

        if temp_message:
            line1 = temp_message
        else:
            line1 = f"Bank {current_bank + 1} {LAYERS[current_bank]['name']}"
            if is_muted:
                line1 = line1[:11].ljust(11) + " MUTE"

        if bg_state == "stopped":
            line2 = "BG: Stopped"
        else:
            icon = ">" if bg_state == "playing" else "||"
            line2 = f"{icon} {pretty_name(BG_TRACKS[bg_index])}"
    display.write(line1, line2)


# --- Энкодер (колбэки приходят из потоков gpiozero) -----------------------
encoder = RotaryEncoder(ENC_A, ENC_B, max_steps=0)
encoder_button = Button(ENC_BTN, pull_up=True, bounce_time=0.03, hold_time=1.0)
_button_was_held = False


def change_volume(direction):
    global volume, is_muted
    with state_lock:
        if is_muted:
            is_muted = False      # вращение снимает Mute
        else:
            volume = round(max(0.0, min(1.0, volume + direction * VOLUME_STEP)), 2)
        apply_volume()
        show_temp(f"Volume: {int(volume * 100)}%")


def on_button_held():
    global is_muted, _button_was_held
    _button_was_held = True
    with state_lock:
        is_muted = not is_muted
        apply_volume()
        show_temp("MUTED" if is_muted else f"Volume: {int(volume * 100)}%")


def on_button_released():
    global _button_was_held, bg_state, ui_dirty
    if _button_was_held:          # это было удержание (Mute), а не клик
        _button_was_held = False
        return
    with state_lock:
        if bg_state == "playing":
            pygame.mixer.music.pause()
            bg_state = "paused"
        elif bg_state == "paused":
            pygame.mixer.music.unpause()
            bg_state = "playing"
        else:
            show_temp("No BG track")
        ui_dirty = True


encoder.when_rotated_clockwise = lambda: change_volume(+1)
encoder.when_rotated_counter_clockwise = lambda: change_volume(-1)
encoder_button.when_held = on_button_held
encoder_button.when_released = on_button_released


# --- Фоновая музыка --------------------------------------------------------
def play_bg(index, direction=1):
    """Запускает трек index; если файл не открывается — пробует следующие
    в направлении direction, чтобы один битый файл не блокировал список."""
    global bg_index, bg_state, ui_dirty
    with state_lock:
        if not BG_TRACKS:
            show_temp("No BG tracks")
            return
        for attempt in range(len(BG_TRACKS)):
            bg_index = (index + attempt * direction) % len(BG_TRACKS)
            path = SOUNDS_DIR / BG_TRACKS[bg_index]
            try:
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.play(-1)
                bg_state = "playing"
                break
            except (pygame.error, FileNotFoundError, OSError) as e:
                print(f"Пропускаю фоновый трек {path}: {e}")
        else:
            pygame.mixer.music.stop()
            bg_state = "stopped"
            show_temp("No BG files")
        ui_dirty = True


def handle_function(fn):
    global current_bank, bg_state, ui_dirty
    with state_lock:
        if fn == "bank_next":
            current_bank = (current_bank + 1) % len(LAYERS)
            ui_dirty = True
        elif fn == "bg_next":
            # Если фон остановлен — первое нажатие запускает текущий трек
            play_bg(bg_index if bg_state == "stopped" else bg_index + 1)
        elif fn == "bg_prev":
            play_bg(bg_index if bg_state == "stopped" else bg_index - 1, direction=-1)
        elif fn == "bg_stop":
            pygame.mixer.music.stop()
            bg_state = "stopped"
            ui_dirty = True


def on_key(r, c):
    bank = current_bank
    cell = LAYERS[bank]["keys"][r][c]
    if not cell:
        return
    if cell["type"] == "function":
        handle_function(cell["function"])
        return
    sound = loaded_banks[bank][r][c]
    if sound:
        sound.play()
        show_temp(pretty_name(cell["file"]))


# --- Матрица клавиш --------------------------------------------------------
cols = [DigitalOutputDevice(pin, initial_value=True) for pin in COL_PINS]
rows = [Button(pin, pull_up=True) for pin in ROW_PINS]
pressed = [[False] * COLS for _ in range(ROWS)]
last_trigger = [[0.0] * COLS for _ in range(ROWS)]


def scan_matrix():
    for c, col in enumerate(cols):
        col.off()                       # активируем столбец (низкий уровень)
        for r, row in enumerate(rows):
            if row.is_pressed:
                if not pressed[r][c]:
                    pressed[r][c] = True
                    now = time.monotonic()
                    if now - last_trigger[r][c] >= RETRIGGER_GUARD:
                        last_trigger[r][c] = now
                        on_key(r, c)
            else:
                pressed[r][c] = False
        col.on()                        # деактивируем столбец
        time.sleep(SCAN_SETTLE)


def _on_sigterm(signum, frame):
    # systemd останавливает сервис сигналом SIGTERM — завершаемся так же чисто, как по Ctrl+C.
    # Повторные SIGTERM (uv пересылает сигнал дочернему процессу) игнорируем.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, _on_sigterm)
    apply_volume()
    display.write("Ready to Play!".center(16), "Press any key".center(16))
    time.sleep(1.5)
    try:
        while True:
            scan_matrix()
            render()
    except KeyboardInterrupt:
        pass
    finally:
        pygame.mixer.stop()
        pygame.mixer.music.stop()
        display.clear()
        print("\nПрограмма успешно остановлена.")


if __name__ == "__main__":
    main()
