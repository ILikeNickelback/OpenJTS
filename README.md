# OpenJTS

Open-source instrument control software for a JTS (Joliot-type Spectrophotometer). Designed for measuring light-induced transient signals in photosynthesis research — ECS, Phi PSII, and related fluorescence and spectroscopy protocols.

---

## Overview

OpenJTS drives two hardware components:

| Component | Role |
|---|---|
| **MCC DAQ ADC board** | High-speed analog data acquisition (200 kHz, 8 channels) |
| **ESP32 microcontroller** | LED sequence timing control via serial |

Two acquisition modes are supported:

- **Sequence mode** — a custom text-based sequence language defines the timing of detection pulses, actinic light steps, and repeats. The decoded sequence is sent to the ESP32 and ADC simultaneously.
- **Frequency mode** — a sinusoidal actinic waveform is generated at a configurable frequency, amplitude, and offset with a defined detection window.

Each mode can be run as a **Fluorescence** or **Spectroscopy** experiment.

---

## Requirements

### Hardware
- MCC DAQ board (compatible with [mcculw](https://github.com/mccdaq/mcculw))
- ESP32 microcontroller connected via USB serial

### Software
- Windows 10/11 (64-bit)
- [pixi](https://prefix.dev/) — used for environment and dependency management

---

## Installation

**1. Install pixi** (if not already installed):

```powershell
iwr -useb https://pixi.sh/install.ps1 | iex
```

**2. Clone the repository:**

```powershell
git clone https://github.com/ILikeNickelback/OpenJTS.git
cd OpenJTS
```

**3. Install the environment:**

```powershell
pixi install
```

This resolves all dependencies from `pixi.toml` using the conda-forge channel, including Python 3.14, NumPy, DearPyGUI, mcculw, loguru, and pyserial.

---

## Running

```powershell
pixi run python software/src/main.py
```

The application opens maximised at 1920×1200. Per-monitor DPI scaling is applied automatically.

---

## Project structure

```
OpenJTS/
├── software/
│   └── src/
│       ├── main.py                   # Entry point
│       ├── config/
│       │   ├── config.json           # ADC, ESP32, LED, and app settings
│       │   ├── sequences.json        # Saved sequence / frequency library
│       │   └── fonts.py              # DPG font setup
│       ├── core/
│       │   ├── app_state.py          # Shared application state
│       │   ├── event_bus.py          # Pub/sub event bus
│       │   ├── layout.py             # Window creation and tab registry
│       │   ├── layout_manager.py     # Panel position/size configuration
│       │   ├── window_base.py        # Base class for all panel windows
│       │   └── workspace_manager.py  # Save / load workspace JSON
│       ├── hardware/
│       │   ├── adc_base.py           # MCC DAQ base driver (buffer, reader thread)
│       │   ├── adc_sequence.py       # Sequence-mode ADC subclass
│       │   ├── adc_frequency.py      # Frequency-mode ADC subclass
│       │   ├── adc_calibration.py    # Calibration ADC subclass
│       │   └── esp32.py              # ESP32 serial driver
│       ├── workers/
│       │   ├── base_worker.py        # Threaded acquisition base class
│       │   ├── sequence_worker.py    # Worker for sequence acquisitions
│       │   ├── frequency_worker.py   # Worker for frequency acquisitions
│       │   └── calibration_worker.py # Worker for 1 Hz LED calibration
│       ├── sequence_builders/        # Sequence language parser and preview builder
│       ├── windows/
│       │   ├── main_window.py        # Top-level DPG window and menu bar
│       │   ├── home_window.py        # Home tab (device status, experiment list)
│       │   ├── experiment/           # Per-experiment tab and sub-tab builders
│       │   ├── panels/               # Control panels (settings, library, metadata…)
│       │   └── plots/                # Lineplot and sequence preview plot
│       └── utils/
├── pixi.toml                         # Dependency manifest
└── pyproject.toml                    # Ruff lint config
```

---

## Configuration

All settings live in `software/src/config/config.json`:

```json
{
  "General":  { "app_name": "JTS", "fontsize": 15 },
  "ADC":      { "board_num": 0, "channel_count": 8, "sampling_rate": 200000 },
  "LED":      { "actinic_light_max": 100, "detection_light_max": 100 },
  "ESP32":    { "baud_rate": 115200, "timeout": 1 },
  "Sampling": { "samples_per_trigger": 8, ... }
}
```

The sequence and frequency preset library is stored in `software/src/config/sequences.json` and is editable directly from the **Sequence library** panel inside the application.

---

## Sequence language

Sequences are written in a compact domain-specific language. A few examples:

| Token | Meaning |
|---|---|
| `D` | Detection pulse |
| `A[100]` | Set actinic light to 100 % |
| `300µsD` | 300 µs detection pulse |
| `4(100msD)` | Repeat `100msD` four times |

Example — ECS measurement:
```
4(100msD) A[100] 50ms A[0] 300µsD 1msD 2msD 5(5msD) 5(10msD) 5(20msD) 5(50msD) 5(100msD)
```

---

## Key features

- **Multiple experiments** — open several experiment tabs simultaneously, each with its own isolated event bus, settings, and results.
- **Averaging and ignore runs** — configurable per sequence: discard N warm-up runs then average M acquisitions.
- **Baseline subtraction** — subtract the mean of the first N points from every result.
- **Live plot** — real-time streaming of incoming ADC data during acquisition.
- **Sample container** — name, toggle, and export individual result series to JSON.
- **Sequence history** — timestamped log of every completed acquisition.
- **Workspace save / restore** — full experiment state (sequences, parameters, results, metadata) saved to JSON and reloadable.
- **Autosave** — a snapshot is written to `software/src/temp/autosave.json` after every completed acquisition.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a large pull request so the change can be discussed first.

The project uses **ruff** for linting:

```powershell
pixi run ruff check software/src
```
