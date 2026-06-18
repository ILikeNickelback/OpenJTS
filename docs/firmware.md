# Firmware

Firmware for the ESP32 microcontroller that drives LED sequence timing, controlled over USB serial from the host application ([`software/src/hardware/esp32.py`](https://github.com/ILikeNickelback/OpenJTS/blob/main/software/src/hardware/esp32.py)). The project lives under `firmware/` and is built with [PlatformIO](https://platformio.org/).

```{note}
This page is a skeleton. The `firmware/` source is still scaffolding (no code committed yet) — fill in each section below as the implementation lands.
```

## Technical choices

*To do: board/chip selection, framework (Arduino vs ESP-IDF), timing strategy, and tradeoffs considered.*

## Serial protocol

The host talks to the ESP32 over a serial connection configured in `software/src/config/config.json`:

| Setting | Value |
|---|---|
| Baud rate | `115200` |
| Timeout | `1` s |

*To do: document the command/response format the firmware expects and emits.*

## Build & flash

```powershell
cd firmware
pio run --target upload
```

*To do: confirm the target board/environment once `platformio.ini` is filled in.*

## Pin mapping

*To do.*
