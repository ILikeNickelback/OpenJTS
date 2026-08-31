# VCCS Design

For this version of the JTS, we are using the analog output of an ADC and a VCCS to control the actinic LED.

---

## What Is a VCCS?

VCCS stands for **Voltage Controlled Current Source**. As the name suggests, it is an electronic circuit that lets you control a current proportionally to a voltage, regardless of what load is connected to the output.

---

## Why a VCCS?

We are using LEDs to produce actinic and detection light. However, LED intensity is not linear with voltage, but with current.

It is possible to use a matrix of resistors and transistors to select light intensity, where each resistor determines the current going through the LED.

Alternatively, we can use the analog output of an ADC — which outputs a voltage from 0 to 10 V with 32,000 possibilities in between — combined with a VCCS. This lets the user select a large range of light intensities with a simple circuit and software controlling the ADC. This design also permits actinic light patterns such as sine waves or anything else.

Alternatively, we could also use a PWM with a VCCS, but this will be explored in a future version.

---

## How to Build a VCCS?

A simple VCCS is composed of the following components:

- A differential or op amp
- A MOSFET or BJT
- A LED (or any current-driven load)
- A sense resistor (or shunt resistor)

R1 and R2 are optional.

### How Does It Work?

As with any amplifier, the circuit continuously compares the input voltage to the feedback loop.

- The input voltage is regulated by the ADC in our case.
- The feedback voltage is proportional to the current going through it (V = I × R).
- Any difference between the two is corrected by the op amp.
- The difference signal drives a transistor that acts as the variable current valve.
- The op amp drives the transistor gate/base until the voltage across R_sense equals V_in, so:

```
I_out = V_in / R_sense
```

### Important Notes

- The LED supply should be powerful enough to drive the LED and sense resistor.
- For a given I_out, a smaller R_sense gives a smaller V_sense, and so a bigger SNR. For example, if you want 100 mA and R_sense = 1 Ω, V_sense = 100 mV. But if R_sense = 0.01 Ω, V_sense = only 1 mV.
- For a given V_in, a bigger R_sense gives better control but more power loss.

---

## Final Design for the JTS

There are some differences from the basic design.

### Voltage Divider

**Constraints**

We are using a 48 V generator with a 38 V LED. The MOSFET uses up around 1–2 V. This leaves around 8 V of headroom for the sense resistor. If we send a 10 V signal to V_in, the signal will saturate at 8 V. Practically, during construction, we observed a saturation level for a signal around 3–4 V.

**Options**

We can either use a larger power supply or add a voltage divider on the analog output to lower V_in.

**Choice**

We are using a voltage divider that lowers V_in by a factor of around 5, so 10 V becomes 2 V.

**Reasons**

Both solutions are possible, but we chose to use a voltage divider because it is simple to make and can be adapted to any power supply.

### MOSFET

The transistor being used is an N-type power MOSFET. It needs to be able to withstand at least 2 A of current and needs a fast switching time. The **IRF540N** fits perfectly for this circuit.

### Op Amp

We are using the **AD797** for this circuit because of its low voltage noise. We had many in stock at the time of making the circuit. It can be substituted for another op amp.

### Sense Resistor

The sense resistor should be small enough to deliver enough power to the actinic light, and big enough that the output signal has a good SNR. The maximum output should be near saturating, but there should also be enough low light levels to perform certain experiments.

We chose **30 Ω** for this resistor, as it fits well with our constraints.

### C1 Capacitor

This capacitor was added to filter out high-frequency noise observed on the photodiode. This high-frequency noise is probably due to the high impedance of the MOSFET gate, which acts like a capacitance. As a result, the MOSFET can open and close in an unpredictable manner. This problem was easily solved by adding a small capacitor between gate and source, filtering out the high-frequency noise.

### R3 and R4 Resistors

These resistors are not mandatory, but they help with stability and avoid ringing.