# Measurement Strategy

As stated before, the JTS works by sending short flashes of non-actinic light. A photodiode captures the light and turns it into a readable voltage via an ADC. You can observe physiological changes of a sample by measuring changes in the light intensity being received.

---

## 1. Sample Timing

It is crucial that the ADC reads a voltage **precisely during the flash of light**. This is easily done by using an external trigger function from the ADC itself or the ESP32.

The sampling point must be chosen carefully:
- **Not too early** in the flash, so as to not waste any of the light being integrated.
- **Not too late**, or digital lag will cause the point to be read after the flash has ended.

In practice, this means a slight delay of about **2-3 µs** before the end of the flash.

---

## 2. DC Component Subtraction

It is important to subtract any DC component that can be present during the measurement. For this, we measure a point just before the flash and subtract it from the point during the flash:

$$I = I_{during} - I_{before}$$

This assumes the baseline is stable over the flash window (a few µs), so any drift in ambient light or LED bias current within that window is not captured by this correction.

---

## 3. Spectrometry Mode

As stated in *Optical Transmission*, when using an "unstable" source of light it was necessary to use two channels to balance out any correlated noise, using the formula:

$$signal = \frac{I_{measurement} - I_{reference}}{I_{reference}}$$

Today, the LEDs used are very stable, and it is possible to use two independent LEDs controlled by the same source. In that case, the two channels no longer share a common noise source, so the formula above no longer cancels shot-to-shot noise the way it did with a single unstable source: the reference channel's noise is uncorrelated with the measurement channel's and simply adds to it instead of subtracting out.

What the reference channel still buys us in this configuration is **drift correction**: it tracks slow, shared-cause changes such as LED aging or temperature-driven intensity shifts over the course of a measurement session, even though it can no longer reject fast, uncorrelated noise. The formula remains useful for that purpose, and since LED stability is now high, the residual noise it introduces is small relative to the signal.

---

## 4. Fluorescence Mode

In fluorescence mode, only **one channel** is needed because the signal is much larger.

---

## 5. Digital Noise Averaging

Finally, to cancel out any digital noise from the ADC, we can use all **8 channels** of the ADC and average them:
- **4** measurement channels
- **4** reference channels

Since ADC noise is uncorrelated across channels, averaging $N$ channels improves the SNR by a factor of $\sqrt{N}$. With $N = 4$, this gives roughly a **2×** reduction in noise for both the measurement and reference signals.
