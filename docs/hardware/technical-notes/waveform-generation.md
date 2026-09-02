# Waveform Generation

OpenJTS produces its actinic and detection light through **two independent paths**:

- The **DAQ board** (an MCC card, driven by [`hardware/adc_base.py`](../../../software/src/hardware/adc_base.py) and its subclasses) generates the full, timing-critical stimulus waveform for real acquisitions — actinic light, detection flashes, and the trigger that tells the acquisition side when to sample — all locked to a single 500 kHz clock.
- The **ESP32** (documented in [Firmware](../../firmware/firmware.md)) is a simpler, general-purpose controller. In the current software it is mostly used for one-shot commands (set a constant actinic level, stop), but its firmware also implements a full standalone sequencer with its own DAC and digital trigger outputs, including a laser trigger the DAQ path does not have.

This note explains how each side actually turns numbers into light, given the channel and resolution constraints each hardware has to work with.

---

## 1. DAQ Board: One 16-bit Waveform, Three Channels, 500 kHz

### 1.1 The channel budget

The board's output scan is started with a single call:

```python
ul.daq_out_scan(
    self.board_num,
    [0, 1, 1],
    [ChannelType.ANALOG, ChannelType.ANALOG, ChannelType.DIGITAL],
    [ao_range, ao_range, ULRange.NOTUSED],
    3,
    self.rate,                       # 500 000 Hz
    self._total_waveform_samples * 3,
    self._memhandle,
    options=(ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS),
)
```

— [`ADCBase.start_acquisition()`](../../../software/src/hardware/adc_base.py)

Three channels, no more: **AO0** (actinic), **AO1** (detection), and one **digital port** (trigger). There is nothing left over for a laser-trigger channel, which is why the DAQ path currently cannot drive a laser — `sequence_waveform_builder.py` parses the `L` (laser) token from a sequence string but its handler is a no-op:

```python
elif item["type"] == "laser":
    pass
```

— [`SequenceWaveformBuilder._parse_sequence` / `build()`](../../../software/src/sequence_builders/sequence_waveform_builder.py)

The ESP32 firmware *does* have two dedicated laser-trigger pins (§2.3) — that logic has simply not been ported to the DAQ-driven waveform yet, because doing so would need a fourth output channel this board doesn't have to spare.

### 1.2 One buffer, interleaved

The board has no concept of "three separate waveforms." It streams a single flat `uint16` array, and consumes it three samples at a time — one value per channel, in channel order, per output tick:

```
index:   0    1    2    3    4    5    6    7    8   ...
         ch0  ch1  ch2  ch0  ch1  ch2  ch0  ch1  ch2  ...
         └── tick 0 ──┘└── tick 1 ──┘└── tick 2 ──┘
```

Both waveform builders ([`SequenceWaveformBuilder`](../../../software/src/sequence_builders/sequence_waveform_builder.py) for the sequence mini-language, [`FrequencyWaveformBuilder`](../../../software/src/sequence_builders/frequency_waveform_builder.py) for sine-modulated acquisitions) build this interleaved array in Python with NumPy strided views (`interleaved[0::3]`, `[1::3]`, `[2::3]`) so each channel can be filled independently before being copied into the DMA buffer:

```python
interleaved = np.empty(total_samples * 3, dtype=np.uint16)
ch0_raw = interleaved[0::3]   # actinic
ch1_raw = interleaved[1::3]   # detection flash
ch2_raw = interleaved[2::3]   # trigger marker
```

Because all three channels are drawn from the *same* buffer at the *same* clock, they are sample-accurate relative to each other — the trigger marker, the detection flash, and the actinic level at any instant are guaranteed to be aligned to within one 2 µs tick (1 / 500 kHz). That's what makes it possible to hit the 2–3 µs sampling window described in [Measurement Strategy](measurement-strategy.md) without any drift between the light and the acquisition trigger.

### 1.3 16-bit resolution, ±10 V range

The board's AO range is bipolar ±10 V, addressed with the full 16-bit count space (`counts_max = 65535`). A percentage intensity (0–100 %) is mapped to a count with:

```python
counts = counts_max * (0.5 + 0.5 * intensity_percent / 100) - offset
```

so 0 % sits near mid-scale count (0 V) and 100 % sits near full-scale count (+10 V) — the same 0.5 + 0.5·x mapping is used for both the actinic channel (ch0) and the detection flash amplitude (ch1). The `offset` term (`actinic_light_offset` / `detection_light_offset` in `config.json`) compensates for the LED driver / VCCS non-linearity described in [VCCS Design](VCCS-design.md).

### 1.4 Channel 0 — actinic light

Ch0 carries whatever actinic waveform the experiment calls for:

- **Sequence mode** — a step function: each `N!` token in the sequence string sets a constant count from that point forward, until the next `N!` token overwrites it (`ch0_raw[current_sample:] = intensity_counts`).
- **Frequency mode** — a genuine sine wave, sampled at the full 500 kHz rate: `sine = amplitude * np.sin(2*np.pi*freq*t + phase) + offset`, converted to counts sample-by-sample. Because the analog output is a real DAC stream and not a switched PWM signal, arbitrary waveforms (sine, or anything else) come for free — this is the same reasoning behind choosing analog output + VCCS over PWM in [LED Control](LED-control.md).

### 1.5 Channel 1 — detection flash

Ch1 stays at 0 except for 20 µs analog pulses (`pulse_width_samples = int(rate * 20e-6)` → 10 samples at 500 kHz), placed either at each `D` token (sequence mode) or on an evenly-spaced grid of `normal_pulses_per_period` flashes per sine period (frequency mode). Because this is a genuine analog channel, the flash amplitude is fully adjustable (`detection_led_intensity`, 0–100 %) — unlike the ESP32's detection output (§2.2), which is only ever fully on or fully off.

### 1.6 Channel 2 — the trigger

Ch2 is digital: each sample is either `0` or `0xFFFF` (all bits of the port driven at once). It is used purely to mark acquisition timing for the AI (input) scan, which is started with `ScanOptions.EXTTRIGGER | RETRIGMODE` — every rising edge on this channel re-arms the input scan and captures `samples_per_trigger` points. Two kinds of markers are written per flash:

- `number_of_points_before_flash` short (10 µs) pre-pulses, 50 µs apart, ending flush with the start of the analog flash — these sample the baseline used for the DC-subtraction described in [Measurement Strategy §2](measurement-strategy.md#2-dc-component-subtraction).
- One pulse during the flash itself, offset 3 samples (6 µs) into it, timed to land just before the flash ends.

So the "3 channels" the DAQ board offers map exactly onto the three physical needs: one analog output for actinic light, one analog output for the detection flash, and one digital line to tell the input side exactly when to look — with no channel left to spare for anything else, laser included.

---

## 2. ESP32: Many Digital Pins, Two 8-bit DACs

The ESP32 firmware ([Firmware](../../firmware/firmware.md)) drives light with completely different building blocks: it has no synchronized multi-channel waveform engine, but it has dozens of general-purpose GPIOs and exactly two on-chip 8-bit DAC channels to work with.

### 2.1 The two onboard DACs

The ESP32 SoC exposes only two analog outputs in hardware, `DAC_CHANNEL_1` (GPIO25) and `DAC_CHANNEL_2` (GPIO26), each 8-bit (0–255 counts). OpenJTS uses only one of them:

| Pin | GPIO | Role |
|---|---|---|
| `actinicDacPin` | 26 | Actinic level — true analog output via `DAC_CHANNEL_2`, `dacWrite()` |
| `detectorDacPin` | 25 | Detector LED — sits on `DAC_CHANNEL_1` but is driven as a **plain digital** GPIO, fully on/off |

So of the two available 8-bit DACs, only the actinic channel is actually used as an analog output. `writeActinicLevel()` also works around a hardware quirk: DAC code 0 still outputs a small non-zero floor voltage (tens to hundreds of mV), enough to keep a sensitive LED driver visibly lit — so a request for level 0 disables the DAC channel entirely and drives the pin `LOW` instead, rather than writing count 0.

Resolution-wise this is much coarser than the DAQ board's 16-bit output (256 levels vs. 65 536), which is acceptable here because the ESP32 path is only ever asked for a static or steppped actinic level (`O<percent>` command, or `N!` inside a sequence) — it has no equivalent to the DAQ's sine-wave modulation, since `dacWrite()` is a single static register write, not a clocked waveform generator.

### 2.2 Detection light is digital-only

The detection LED pin (GPIO25) is capable of being a DAC, but the firmware never uses it that way — it is toggled with direct `GPIO_SET`/`GPIO_CLR` register writes for speed, fully on for a fixed 18 µs window and fully off otherwise (`detection_trigger()`). There is no equivalent of the DAQ board's adjustable detection-flash amplitude (§1.5): on the ESP32 path, the detection flash is binary, and its "channel" is really just one digital output line rather than an analog one.

### 2.3 A lot of digital pulse outputs

Beyond the one analog channel, the firmware drives everything else — trigger and laser synchronization — as plain digital pulses, using direct register writes rather than `digitalWrite()` so edges stay sharp at microsecond timescales:

| Pin | GPIO | Role |
|---|---|---|
| `TriggPin` | 12 | Brackets a detection event with two short pulses, for an external DAQ |
| `laserChannel_open` | 18 | Laser channel "open" trigger pulse |
| `laserChannel_start` | 19 | Laser channel "start" trigger pulse |

`setup()` maxes out pad drive strength (`GPIO_DRIVE_CAP_3`) on all four pulse-critical pins so their edges stay sharp even while the actinic LED's current draw sags the supply rail. Because the ESP32 exposes dozens of GPIOs in total, this scheme could in principle be extended with more digital trigger lines (further laser channels, additional external sync outputs, etc.) at essentially no hardware cost — the constraint on this path is not "how many pins are available" the way it is on the DAQ board, but simply which ones the firmware currently wires up.

`laser_trigger()` is the one capability that exists here and not on the DAQ side: it pulses `laserChannel_open` high for 10 µs, waits 160 µs, then pulses `laserChannel_start` high for 10 µs — a fixed two-edge handshake a laser's own controller can use to fire in sync with the sequence, something the 3-channel DAQ waveform (§1.6) has no spare channel to reproduce.

### 2.4 Summary: two different trade-offs

| | DAQ board | ESP32 |
|---|---|---|
| Output channels | 3 total (2 analog + 1 digital), fixed by the scan call | Dozens of GPIO, 2 onboard 8-bit DACs (only 1 used) |
| Resolution | 16-bit (65 536 counts) on both analog channels | 8-bit (256 counts) on the one DAC used |
| Sample rate | 500 kHz, single shared clock across all 3 channels | No fixed clock — pulses are timed procedurally in firmware |
| Detection flash | Analog, adjustable amplitude | Digital, on/off only |
| Actinic waveform | Arbitrary (step or sine), sample-accurate | Step changes only |
| Laser control | Not wired (no spare channel) | Two dedicated trigger pins |

The two paths are complementary rather than redundant: the DAQ board buys synchronized, high-resolution, arbitrary-waveform light generation at the cost of a hard 3-channel ceiling; the ESP32 buys effectively unlimited digital I/O (including laser triggering) at the cost of coarser, non-synchronized analog control.
