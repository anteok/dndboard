# DnD Soundboard (Raspberry Pi 3B)

6x14 key matrix (with diodes) + LCD 1602A (I2C) + EC11 encoder. Sound layout is in `keymap.py`, sound files go in `sounds/`.

## Raspberry Pi setup (once)

1. Use **Raspberry Pi OS 64-bit** (Bookworm). pygame has ready wheels for aarch64; on 32-bit it would have to be compiled.
2. `sudo raspi-config` → Interface Options:
   - **I2C** → Enable (display)
   - **Serial Port** → login shell: **No**, serial hardware: **No** (GPIO 14/15 are used by the matrix)
   - **SPI** → Disable (GPIO 7, 9, 10, 11 are used by the matrix)
3. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. In the project folder: `uv sync` — uv downloads Python 3.11 and installs everything into `.venv`.

## Run

```
uv run soundboard.py          # soundboard
uv run soundboard.py --map    # print the key layout (works on any PC)
```

Display not showing anything? Check its address with `i2cdetect -y 1` (usually `0x27`, sometimes `0x3F`) and pass it to `LCD(address=...)`.

## Sound quality

The Pi 3's 3.5 mm jack is a PWM output: some hiss and buzz is normal for it. In order of effect:

1. `alsamixer` → F6 → pick **Headphones** → set PCM to **0 dB** (shown at the top). Anything above 0 dB distorts.
2. Use the official 5 V / 2.5 A power supply, and don't power the speakers from the Pi's USB (that causes a ground-loop whine).
3. Best fix: a cheap **USB sound card**. An I2S DAC HAT won't work here because its pins (GPIO 18–21) are used by the matrix and encoder. Plug it in, run `uv run soundboard.py --audio-devices`, and put its name into `AUDIO_DEVICE` in `soundboard.py`.

Crackles or clicks: raise `AUDIO_BUFFER` to 2048. Distortion when many sounds overlap: lower `SFX_GAIN` / `MUSIC_GAIN`.

## Autostart

The project ships a systemd **user** service (`dndboard.service`). It expects the project at `~/dndboard`; if it's elsewhere, edit `WorkingDirectory`.

```
mkdir -p ~/.config/systemd/user
cp ~/dndboard/dndboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dndboard
sudo loginctl enable-linger $USER     # start at boot, without anyone logging in
```

Check that the user is in the hardware groups (default user on Raspberry Pi OS already is): `groups` should list `gpio`, `i2c` and `audio`.

Everyday commands:

```
systemctl --user status dndboard      # is it running?
journalctl --user -u dndboard -f      # live log (missing files, errors)
systemctl --user restart dndboard     # after editing keymap.py or the code
systemctl --user disable --now dndboard   # turn autostart off
```

If it crashes, systemd restarts it after 3 seconds.
