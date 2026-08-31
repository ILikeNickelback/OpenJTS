# Technical choices: LED control

The JTS uses two types of LED:

- LEDs for the detection light
- LEDs for the actinic light

## 1. Detection LED

**Requirements:**

- The colour is chosen according to what the user wants to observe.
- The LED must deliver a clean, stable, short and powerful light pulse of a defined intensity.

### 1.1 Colour

**Constraint.** The emission colour must match the requirements of the experiment, both in wavelength and in intensity (for example, blue for fluorescence measurements).

**Options.**

The first option is to use an LED of exactly the colour required, for example a blue LED for fluorescence. This works well if several LEDs of different colours are mounted together and selected by software, but it means either a controller with many PWM outputs, each with its own transistor and resistor, or an equivalent array of transistors and resistors. A single LED can also turn out to be too weak for the measurement.

The second option is to use an LED array with a flat spectral output across the visible range (400–800 nm) and to select the colour with filters, for example a blue filter for fluorescence. Only one controller output is then needed to drive the LED, which greatly simplifies the electronics. The trade-off is that a good filter set is required, and some residual light outside the wanted band is always transmitted.

The two approaches can also be combined: single-colour LEDs together with filters.

**Choice.** For the OpenJTS model we use a single array of white LEDs (Sunlike COB) together with coloured filters.

**Reason.** Sunlike COB LEDs are cheap, easy to drive and have a flat spectral output. Coloured filters are easy to obtain and easy to use.

### 1.2 Intensity

**Constraint.** The LED must be able to deliver pulses as short as 20 µs, with enough power and good stability.

**Options.**

A short, powerful pulse of a defined intensity requires a powerful LED and one of the following drive schemes: a controller with an array of transistors and resistors, PWM through a single transistor and resistor, or an analogue output driving a single transistor and resistor or a VCCS. Whichever is chosen, the driver must be able to produce a clean 20 µs pulse.

A few practical points:

- A 100 Ω resistor on the output limits ringing.
- A MOSFET is recommended as the switching element.
- A fairly low resistor (10–100 Ω) between the drain and the power supply gives the best compromise between power and stability.
- The power supply must be able to drive the LED and deliver enough power; it can be linear or switching.
- Supply filtering with a one- or two-stage filter is essential for stable pulses.
- A gate driver can also be used to obtain a clean, stable pulse at the gate.

**Choice.** For the detection LED we use a switching 48 V power supply with a two-stage filter, an IRF540N MOSFET and a 50 Ω shunt resistor. A gate driver has not been tested yet.

**Reasons.** The LED we selected needs at least 38 V, so the supply was chosen with enough headroom and with the ability to deliver high power during short pulses. Since a switching supply is relatively noisy, a two-stage filter is used to cut high-frequency noise; this is critical given the very short pulses and the high instantaneous load. The IRF540N handles the required power, is quiet and switches fast. The 50 Ω shunt resistor was chosen empirically, as it gives enough power while keeping the pulse stable. A gate driver has not yet been evaluated.

**Further notes.** Because of the large load and the fast switching, the circuit shows significant stray inductance, which perturbs the output voltage of the transimpedance amplifier (V = −L × dI/dt). The actinic and detection ground return paths must therefore be properly separated.

## 2. Actinic LED

**Requirements:**

- The colour is chosen according to what the user wants to observe.
- The length and intensity of the pulse must be easy to change.
- It must be possible to send amplitude-modulated light.

### 2.1 Colour

**Constraint.** The colour is chosen according to what the user wants to observe.

**Options.** An array of LEDs of different colours (for example red, far red or blue) can be used, with the active colour selected either manually or digitally. Depending on their characteristics, the different colours may need different power supplies.

**Choice.** We currently use an array of blue, red and far-red LEDs. All colours sit on a single chip, but each has its own power cable; the user selects a colour by plugging in the corresponding cable.

**Reason.** The user can change the actinic colour quickly.

**Note.** The new model currently provides red light only, as this is the most frequently used colour.

### 2.2 Length and intensity

**Constraint.** The user must be able to set the length and the intensity of the actinic light within a sequence. These values are programmed in advance, in the sequence itself: the intensity cannot be changed in real time while the sequence is running. Actinic pulses are comparatively long, from a few milliseconds to several seconds, so stability matters much less than it does for the detection LED. The LED array we designed runs from a 15 V supply, linear or decoupled; filtering is not needed but encouraged given the pulse lengths.

**Options.** A controller with an array of transistors and resistors, PWM through a single transistor and resistor, or an analogue output driving a VCCS.

**Choice.** We currently use an analogue output driving a VCCS, with a 15 V linear power supply.

**Reasons.** This combination gives access to a wide range of light intensities and full control over the pulse length. We do not use a PWM signal because it relies on a system that simulates analogue outputs by switching on and off at very fast frequencies. This may be a hindrance to biological publishing.

### 2.3 Amplitude modulation

**Constraint.** The user must be able to send modulated actinic light, for example a sinusoidal waveform.

**Options.** PWM, or an analogue output driving a VCCS.

**Choice.** Analogue output with a VCCS.

**Reason.** An analogue signal is continuous, whereas PWM is not.