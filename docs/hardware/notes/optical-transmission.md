# Optical Transmission

## Background

The first JTS designs used xenon flash lamps to produce the detection flashes. Xenon lamps give short and powerful flashes, but they are very unstable from one flash to the next. This is a real problem in differential spectroscopy: the absorption changes being measured are small, so fluctuations in the intensity of the detection light are enough to hide them.

The solution was to send the same flash to two channels and normalise one against the other. One channel holds the sample (the **measurement channel**); the other holds only a shutter (the **reference channel**), used to balance the light intensity between the two. At each time point, the reference is subtracted from the measurement and the result is divided by the reference:

```
signal = (I_measurement − I_reference) / I_reference
```

Any variation common to both channels therefore cancels out.

---

## Detection Flashes

### Constraint

The detection flashes must be stable, powerful, and synchronised between the two channels.

### Options

Two optical designs have historically been used to bring the same detection light to both channels:

- A semi-reflecting mirror (beam splitter)
- A Y-shaped optical fibre

Each has advantages and drawbacks.

A third option is to use two separate LEDs controlled by the same circuit. In this case, normalisation only rejects supply- and driver-level noise, not LED-level noise — though this is likely acceptable given how stable modern LEDs are.

### Choice

Two modern LEDs, one per channel, driven by the same circuit.

### Reasons

Modern LEDs are far more stable than xenon lamps and are powerful enough for the measurement, so the flash no longer needs to be split from a single source. In addition, the actinic light is not transmitted through fibre optics, avoiding the need for an expensive fibre optic component.

---

## Light Filters

### Constraints

The detection flashes and actinic flashes must be filtered correctly according to the experiment the user wants to run.

### Options

For the detection light, previous JTS models used one of the following:

- A monochromator
- A VariSpec (liquid crystal tunable filter)
- A choosable detection light array offering many colors
- Flat round filters
- Double linear filter

### Choice

For the OpenJTS, we will use **flat round filters**.

### Reasons

This is the cheapest and simplest way to filter the detection light.

---

## Photodiode

### Constraint

We need to precisely measure light intensity from 20 µs pulses with the best possible signal-to-noise ratio (SNR).

### Options

When choosing a photodiode, several attributes come into play:

- **Photosensitive area** — determines how many photons will be captured; a larger surface yields more signal.
- **Spectral response range** — must cover the entirety of the desired spectral range.
- **Terminal capacitance** — determines response speed; lower capacitance increases bandwidth.
- **Reverse voltage** — reverse voltage lowers terminal capacitance and increases bandwidth, but also increases dark noise.
- **Dark current** — current noise present when the photodiode is in the dark.

Many different models are possible.

### Choice

We used the Hamamatsu Si PIN photodiode **[S ….. BQ]**, reverse-biased at 48 V.

### Reasons

This model has one of the largest photosensitive areas, a good spectral response range, and a low terminal capacitance. In addition, a 48 V reverse bias drops the terminal capacitance to 47 pF, which suits our 20 µs pulses well. The resulting dark current of a few nA is negligible.