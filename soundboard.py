#!/usr/bin/env python3
"""DnD Soundboard для Raspberry Pi 3B.

Железо: матрица клавиш 6x14 с диодами, LCD 1602A по I2C, энкодер EC11 с кнопкой.

Управление:
  [0][0]          — следующий банк звуков (по кругу)
  [5][0] / [5][1] — фоновый трек назад / вперёд (запускает воспроизведение)
  [5][2]          — стоп фоновой музыки
  Энкодер: вращение — громкость, короткое нажатие — пауза/продолжить фон,
           удержание 1 с — Mute (вращение снимает Mute)

Раскладка звуков — в keymap.py.
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
from keymap import BANKS, BG_TRACKS  # noqa: E402

SOUNDS_DIR = BASE_DIR / "sounds"

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

ROWS, COLS = len(ROW_PINS), len(COL_PINS)
KEY_BANK = (0, 0)
KEY_BG_PREV = (ROWS - 1, 0)   # нижний левый угол
KEY_BG_NEXT = (ROWS - 1, 1)
KEY_BG_STOP = (ROWS - 1, 2)
SPECIAL_KEYS = {KEY_BANK, KEY_BG_PREV, KEY_BG_NEXT, KEY_BG_STOP}

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


def pretty_name(path):
    """'fight/sword_clash_01.ogg' -> 'Sword Clash 01'; '01_beginning_into...' -> 'Beginning Into...'"""
    stem = Path(path).stem
    parts = stem.split("_")
    if len(parts) > 1 and parts[0].isdigit():
        parts = parts[1:]
    return " ".join(p.capitalize() for p in parts)


def check_keymap():
    """Предупреждает, если раскладка в keymap.py не совпадает с размером матрицы."""
    for b_idx, bank in enumerate(BANKS):
        keys = bank["keys"]
        if len(keys) != ROWS or any(len(row) != COLS for row in keys):
            shape = f"{len(keys)}x{max((len(r) for r in keys), default=0)}"
            print(f"Внимание: банк {b_idx + 1} ({bank['name']}) имеет размер {shape}, "
                  f"а матрица {ROWS}x{COLS}. Лишние клавиши игнорируются, недостающие пустые.")


def key_file(bank, r, c):
    keys = BANKS[bank]["keys"]
    if r < len(keys) and c < len(keys[r]) and (r, c) not in SPECIAL_KEYS:
        return keys[r][c]
    return None


check_keymap()


def print_map():
    labels = {KEY_BANK: "<< BANK >>", KEY_BG_PREV: "<< BG PREV >>",
              KEY_BG_NEXT: "<< BG NEXT >>", KEY_BG_STOP: "<< BG STOP >>"}
    for b_idx, bank in enumerate(BANKS):
        print(f"\n=== Банк {b_idx + 1}: {bank['name']} ===")
        for r in range(ROWS):
            for c in range(COLS):
                if (r, c) in labels:
                    label = labels[(r, c)]
                else:
                    f = key_file(b_idx, r, c)
                    label = pretty_name(f) if f else "-"
                print(f"  [{r}][{c:>2}] {label}")
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
    wanted = sorted({key_file(b, r, c) for b in range(len(BANKS))
                     for r in range(ROWS) for c in range(COLS)} - {None})
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
        [[cache.get(key_file(b, r, c)) for c in range(COLS)] for r in range(ROWS)]
        for b in range(len(BANKS))
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
            line1 = f"Bank {current_bank + 1} {BANKS[current_bank]['name']}"
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


def handle_special_key(key):
    global current_bank, bg_state, ui_dirty
    with state_lock:
        if key == KEY_BANK:
            current_bank = (current_bank + 1) % len(BANKS)
            ui_dirty = True
        elif key == KEY_BG_NEXT:
            # Если фон остановлен — первое нажатие запускает текущий трек
            play_bg(bg_index if bg_state == "stopped" else bg_index + 1)
        elif key == KEY_BG_PREV:
            play_bg(bg_index if bg_state == "stopped" else bg_index - 1, direction=-1)
        elif key == KEY_BG_STOP:
            pygame.mixer.music.stop()
            bg_state = "stopped"
            ui_dirty = True


def on_key(r, c):
    if (r, c) in SPECIAL_KEYS:
        handle_special_key((r, c))
        return
    bank = current_bank
    sound = loaded_banks[bank][r][c]
    if sound:
        sound.play()
        show_temp(pretty_name(key_file(bank, r, c)))


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
