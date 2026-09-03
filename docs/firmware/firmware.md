# Firmware

## What It Is

The OpenJTS firmware runs on an **ESP32** (`esp32dev` board) and is built with **PlatformIO** using the **Arduino** framework (see [`platformio.ini`](../../firmware/platformio.ini)). It is a small, non-blocking state machine that listens for text commands over USB serial and, in response, drives the instrument's actinic LED, detector LED, and laser trigger outputs with microsecond-level timing. The desktop application (see [Software Architecture](../software/architecture.md)) is the only intended sender of these commands.

---

## Source Layout

The firmware folder contains the main.cpp file, a plateformio.ini file and a lib folder.
Each folder is composed of
-a header file (.h) that is used for :...
-a C++ file (.cpp) that is used for :... 


```
firmware/
├── platformio.ini              # esp32dev / Arduino framework
├── src/main.cpp                # This file containes : setup()/loop(), pin init, state dispatch
└── lib/
    ├── config/                 # This file containes :
    ├── system_context/         # This file containes :
    ├── serial_comm/            # This file containes :
    ├── hardware/               # This file containes :
    └── states/                 # This file containes :
```


## Hardware Pins

Pin assignments live in [`lib/config/config.h`](../../firmware/lib/config/config.h).

| Pin | GPIO | Role |
|---|---|---|
| `TriggPin` | 12 | Digital trigger pulses bracketing a detection event (e.g. for synchronizing an external DAQ) |
| `actinicDacPin` | 26 | Actinic light level — DAC output (`DAC_CHANNEL_2`) |
| `detectorDacPin` | 25 | Detector LED — plain digital GPIO, driven fully on/off |
| `laserChannel_open` | 18 | Laser channel "open" trigger pulse |
| `laserChannel_start` | 19 | Laser channel "start" trigger pulse |

`TriggPin` was deliberately moved from GPIO25 to GPIO12 to free GPIO25 for the detector LED, which needs the GPIO matrix's push-pull output stage for sharp edges. On boot, `setup()` maxes out the pad drive strength on all four pulse pins (`GPIO_DRIVE_CAP_3`) so their edges stay sharp even when the actinic LED's current draw sags the rail, and immediately forces the actinic output to a true 0 V so nothing is left floating before the first command arrives.

### Actinic level (DAC quirk)

The ESP32's DAC has a non-zero floor voltage at code 0 (tens to hundreds of mV) — enough to keep a sensitive actinic LED driver visibly lit. `writeActinicLevel()` (in [`lib/states/states.cpp`](../../firmware/lib/states/states.cpp)) works around this: a value of 0 disables the DAC channel and drives the pin as a plain digital `LOW`, while any other value uses `dacWrite()` (8-bit, 0–255).

---

## Serial Protocol

Every message is framed as `<...>`: a `startMarker` (`<`) resets the input buffer, an `endMarker` (`>`) marks the message complete. Framing and buffering are handled by [`readSerial()`](../../firmware/lib/serial_comm/serial_comm.cpp), which is polled once per `loop()` iteration and is non-blocking.

The first character of a framed message selects the command; markers are defined in `config.h`:

| Marker | Char | Meaning |
|---|---|---|
| `continuesMarker` | `#` | Enter continuous-flash mode; digits after it set the flash interval in ms (e.g. `<#200>`) |
| `constantLightMarker_on` | `O` | Enter constant-light mode; digits after it set the actinic level as a percentage (e.g. `<O75.5>`) |
| `constantLightMarker_off` | `I` | Reserved for turning constant light off — defined but not currently read by the state machine (send `<O0>` instead) |
| `set_LED_intensity` | `S` | While in continuous-flash mode, set detector LED intensity as a percentage (e.g. `<S50>`) |
| `stopMarker` | `X` | Abort — only recognized mid-wait during a sequence delay |
| *(digit)* | `0`–`9` | Start a sequence-acquisition message (see below) |

---

## State Machine

`ctx.state` (in [`lib/system_context/system_context.h`](../../firmware/lib/system_context/system_context.h)) drives a `switch` in `loop()`. Handlers live in [`lib/states/states.cpp`](../../firmware/lib/states/states.cpp).

- **IDLE** (`handleIdle`) — the default/resting state. Waits for a framed message and dispatches based on its first character: `#` → CONTINUES_FLASH, `O` → CONSTANT_LIGHT, a leading digit → SEQUENCE_ACQUISITION.
- **CONTINUES_FLASH** (`handleContinuesFlash`) — repeatedly calls `detection_trigger()` once per second. An `S` message updates the (currently unused by hardware, see below) detector intensity setting; any other message returns to IDLE.
- **CONSTANT_LIGHT** (`handleConstantLight`) — parses the percentage from the buffer, converts it to a DAC code, calls `writeActinicLevel()`, and returns to IDLE. This is a one-shot: the state exists only to interpret the `O` message's payload before falling back to IDLE.
- **SEQUENCE_ACQUISITION** (`handleSequence`) — parses and executes a compact sequence mini-language from the buffer, then returns to IDLE.

### Sequence mini-language

`handleSequence()` scans the message character by character:

| Token | Effect |
|---|---|
| `D` | Fire `detection_trigger()` |
| `L` | Fire `laser_trigger()` |
| `<number>!` | Set the actinic level to `<number>`% immediately (no delay) |
| `<number>` (no `!`) | Wait `<number>` ms, abortable — if an `<X>` message arrives during the wait, the sequence stops immediately |

Waits are implemented by `waitAbortable()`, which sleeps in 1 ms chunks and polls serial between each one, so a stop command can interrupt a long wait instead of blocking behind a single `delayMicroseconds()` call. After the sequence ends (normally or via abort), the actinic output is restored to `currentActinicPWM` and the state returns to IDLE.

---

## Trigger Timing

Both trigger routines live in [`lib/hardware/hardware.cpp`](../../firmware/lib/hardware/hardware.cpp) and use direct `GPIO_SET`/`GPIO_CLR` register writes (defined in `config.h`) rather than `digitalWrite()`, for speed.

- **`detection_trigger()`** — pulses `TriggPin` high for 2 µs, then holds `detectorDacPin` high for 18 µs (lighting the detector LED), then pulses `TriggPin` high for 2 µs again before clearing the detector LED. The two `TriggPin` edges bracket the detection window for an external DAQ.
- **`laser_trigger()`** — pulses `laserChannel_open` high for 10 µs, waits 160 µs, then pulses `laserChannel_start` high for 10 µs.

---

