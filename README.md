# DnD Soundboard (Raspberry Pi 3B)

6x14 key matrix (with diodes) + LCD 1602A (I2C) + EC11 encoder. Sound files go in `sounds/`. The key layout lives in `dndboard.db` (SQLite) and is edited in the web UI; `keymap.py` is only the starting layout.

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
uv run webapp.py              # web UI on port 80, see "Web UI" below
```

Display not showing anything? Check its address with `i2cdetect -y 1` (usually `0x27`, sometimes `0x3F`) and pass it to `LCD(address=...)`.

## Web UI

`webapp.py` is a separate web service that runs alongside the soundboard and never touches the hardware.

- **Layout** tab: every layer as a 6x14 grid. Click a key to put a sound, a player function (Next bank, BG prev / next / stop) or nothing on it. Changed keys get a red dot; edits stay in the browser until you press **Save & restart soundboard**, which writes them to `dndboard.db` and restarts the soundboard so it loads the new layout. Every layer needs a *Next bank* key (otherwise you'd be stuck on it), so Save refuses a layout without one.
- **Sound banks** tab: the subfolders of `sounds/`, their tracks and which keys use them. Missing files are marked red.
- **Listening**: every sound has a ▶ button (on its key, in the key editor's list, in the bank lists and in the background track list) that plays it **in the browser** for a preview; the board itself stays silent. Press it again to stop. Ogg files play in Chrome, Firefox and on Android; older iPhones/iPads may not play Ogg.
- **Uploading sounds** (Sound banks tab): drop `.ogg`, `.wav`, `.mp3` or `.flac` files on the page, pick an existing bank or type a new bank name, and press Upload. File and bank names are tidied up for the LCD (lowercase, plain Latin letters: `Гром (2).OGG` → `grom_2.ogg`). A file with the same name is only replaced if you tick *Replace*. Files are checked to really be audio, max 100 MB each (`DNDBOARD_MAX_UPLOAD_MB`), and at least 100 MB is always left free on the SD card. Uploading doesn't touch the layout: put the new sound on a key and Save. Replacing a sound that is already on a key takes effect at the next Save (restart). 44.1 kHz files play best; other rates work but are resampled.

### Where the layout is stored

`dndboard.db` (SQLite, next to the code; not in git). The first time either service starts, it is created from `keymap.py`. After that `keymap.py` is not read any more. To start over from `keymap.py`, stop both services and delete `dndboard.db`. Back up the layout with `cp dndboard.db dndboard.db.bak`.

Save restarts the soundboard with `systemctl --user restart dndboard`, so both services must run as the same user (the default with the instructions below). Another command can be set with the `DNDBOARD_RESTART_CMD` environment variable. If the restart fails (e.g. when trying it on a PC), the layout is still saved and the page says so.

```
uv run webapp.py              # http://<pi-address>/  (port 80)
uv run webapp.py --port 8080  # any other port, e.g. to try it on a PC
```

Port 80 is privileged on Linux. Let normal users open it (once):

```
echo 'net.ipv4.ip_unprivileged_port_start=80' | sudo tee /etc/sysctl.d/99-dndboard-web.conf
sudo sysctl --system
```

Autostart works like the main service:

```
cp ~/dndboard/dndboard-web.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now dndboard-web
journalctl --user -u dndboard-web -f
```

JSON API: `GET/PUT /api/layout`, `GET /api/sounds`, `POST /api/sounds/upload`, sound files at `/sounds/<bank>/<file>`; interactive docs at `/api/docs`.

The web UI has no password: anyone on the same network can change the layout and upload files. Keep the Pi on a network you trust.

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
systemctl --user restart dndboard     # after changing the code (the web UI's Save does this for layout changes)
systemctl --user disable --now dndboard   # turn autostart off
```

If it crashes, systemd restarts it after 3 seconds.
