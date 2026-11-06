# DnD Soundboard (Raspberry Pi 3B)

5x12 key matrix + LCD 1602A (I2C) + EC11 encoder. Sound layout is in `keymap.py`, sound files go in `sounds/`.

## Raspberry Pi setup (once)

1. Use **Raspberry Pi OS 64-bit** (Bookworm). pygame has ready wheels for aarch64; on 32-bit it would have to be compiled.
2. `sudo raspi-config` → Interface Options:
   - **I2C** → Enable (display)
   - **Serial Port** → login shell: **No**, serial hardware: **No** (GPIO 14/15 are used by the matrix)
3. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. In the project folder: `uv sync` — uv downloads Python 3.11 and installs everything into `.venv`.

## Run

```
uv run soundboard.py          # soundboard
uv run soundboard.py --map    # print the key layout (works on any PC)
```

Display not showing anything? Check its address with `i2cdetect -y 1` (usually `0x27`, sometimes `0x3F`) and pass it to `LCD(address=...)`.
