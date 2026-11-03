# Sequence language

A sequence describes, step by step, what the instrument does during one run: when to fire a detection pulse, how long to wait, and when to change the actinic light. You write sequences in the **Sequence input** box of a Sequence experiment.

Example (ECS measurement):

```
4(100msD) A[100] 50ms A[0] 300µsD 1msD 2msD 5(5msD) 5(10msD) 5(20msD) 5(50msD) 5(100msD)
```

Read it left to right: four detection pulses 100 ms apart, then the actinic light switches to 100% for 50 ms, then it switches off, and detection pulses follow at increasing intervals.

---

## Elements

| Element | Example | Meaning |
|---|---|---|
| Delay | `100ms`, `300µs`, `2s` | Wait this long before the next step |
| Detection | `100msD` | Wait, then fire one detection pulse. Each `D` produces one measured point. |
| Actinic level | `A[100]`, `A[10.58]`, `A[0]` | Set the actinic light to N% (0–100, decimals allowed). Takes no time. |
| Laser | `10msL` | Wait, then fire the laser trigger |
| Repeat | `4(100msD)` | Repeat the contents of the brackets N times |

### Time units

| Unit | Meaning |
|---|---|
| `s` | seconds |
| `ms` | milliseconds |
| `µs` or `us` | microseconds |
| *(no unit)* | milliseconds |

Decimals are allowed: `1.5msD`.

### Repeats

`N(...)` repeats its contents N times. Repeats can be nested:

```
3(2(10msD) 50msD)
```

expands to `10msD 10msD 50msD`, three times.

### Spaces and line breaks

Spaces and line breaks are ignored, so you can lay out long sequences over several lines:

```
10(500msD)
A[100] 150ms A[0]
300usD 4(25msD) 10(500msD)
```

---

## Rules to avoid surprises

The decoder silently ignores anything it does not understand: it does **not** show an error. Use **Visualize** to check that the preview matches what you meant, and keep these rules in mind.

**1. `D` and `L` must directly follow a number.**
`100msD` is a delay then a detection. A `D` on its own, for example `A[100]D`, is dropped. Write `A[100]0msD` or put a delay before it.

**2. Always write `A` before `[N]`.**
`50msA[0]` works. `50ms[0]` is read correctly by the DAQ, but in ESP32 mode the delay and the level merge into `50.00!`, so the light is set to 50% and the delay is lost.

**3. Two delays in a row are not added together on the ESP32.**
Write `50.3ms`, not `50ms300us`. On the ESP32, the second delay is lost.

**4. Actinic levels must be whole numbers from 0 to 100.**
`A[50.5]` is not recognised: `50.5` is read as a 50.5 ms delay instead. Values above 100 are not limited and give wrong light levels.

**5. Use the micro sign `µ` (or simply `us`).**
The Greek letter `μ` looks the same but is not recognised. `300μsD` becomes a 300 ms delay with no detection. When in doubt, type `us`.

**6. Do not start a sequence with `T`.**
`T` is accepted by the decoder but has no effect at the moment. In ESP32 mode, a sequence that starts with `T` is not run at all.

---

## Timing details

- Each detection pulse lasts about **20 µs**. This time is added after each `D`, so `5(100msD)` lasts 5 × 100.02 ms.
- An actinic change (`A[N]`) happens instantly at that point in the sequence and lasts until the next `A[...]`.
- At the end of a sequence, the actinic light goes back to the background level set in the **Actinic Light** panel.
- The time axis of the results starts at 0 at the beginning of the sequence. Each point is placed at the moment its `D` fires.

---

## What happens to a sequence

When you click **Load sequence**, each sequence string is decoded into a list of tokens:

```
4(100msD) A[100] 50ms A[0] 300µsD
```

becomes

```
100.0  D  100.0  D  100.0  D  100.0  D  100!  50.0  A  0!  0.3  D
```

- Numbers are delays in milliseconds.
- `N!` sets the actinic light to N%.
- `D` and `L` are detection and laser pulses.

What happens next depends on `General.hardware` in `config.json`:

- **`"ESP32"`**: the tokens are sent to the ESP32, which plays the sequence and fires the LEDs. The DAQ board records one block of samples per trigger. See [Firmware](../firmware/firmware.md) for the exact message format.
- **`"ADC"`**: the DAQ board turns the tokens into analog output waveforms (actinic level, detection pulses, trigger markers) and plays and records them itself. The laser (`L`) is not implemented in this mode.

The decoder is in `software/src/sequence_builders/sequence_decoder.py`.

---

## Example protocols

These are included in the sequence library.

**ECS**

```
4(100msD)A[100]50msA[0]300µsD1msD2msD5(5msD)5(10msD)5(20msD)5(50msD)5(100msD)
```

**Phi PSII**

```
10(500msD)
A[0]
4(25msA[0]300µsD50usA[0])
2(50msA[0]300µsD50usA[0])
3(100msA[0]300µsD50usA[0])
60(500msA[0]300µsD50usA[0])
A[100]150msA[0]
300usD50usA[100]50msA[0]
300usD50usA[100]50msA[0]
300usD50usA[100]50msA[0]
300usD50usA[100]50msA[0]
300usD
4(25msD)
4(100msD)
10(500msD)
```
