# Transimpedance Amplifier Design

The transimpedance amplifier (TIA) is a critical building block of the JTS optical detection system. It is responsible for converting the photocurrent emitted by the photodiode into a stable, low-noise voltage readable by the Data Acquisition (DAQ) system.

A useful baseline reference on stable TIA design principles is available via [DigiKey's TIA Design Guide](https://www.digikey.fr/fr/articles/how-to-design-stable-transimpedance-amplifiers-automotive-medical-systems).

---

## 1. System Specifications & Constraints

Designing the TIA requires balancing **gain, bandwidth, and linearity**. A primary challenge is managing the wide dynamic range of optical signals: varying optical filters or samples significantly changes light transmission. The TIA gain must resolve small signals without saturating under peak light levels (though light intensity from the excitation LED can be modulated).

### Photodiode Characteristics
Based on the photodiode specifications, the sensor is a Hamamatsu Si PIN photodiode reverse-biased at **48 V**, yielding:
- **Terminal Capacitance ($C_d$):** $\approx 47\text{ pF}$
- **Dark Current:** Negligible (a few nA)

### Bandwidth Target
To resolve a **20 µs** light pulse without excessive edge rounding, the amplifier's rise time ($t_r$) should be roughly $\frac{1}{17}$ of the pulse width:

$$t_r \approx \frac{20\text{ }\mu\text{s}}{17} \approx 1.2\text{ }\mu\text{s}$$

$$f_{-3\text{dB}} = \frac{0.35}{t_r} \approx 300\text{ kHz}$$

We establish **300 kHz** as the minimum closed-loop bandwidth target for every gain range.

### Feedback Resistance Choice
The highest expected photocurrent is around **50 µA**. The ADC can accept up to **+10 V**, so the maximum allowable feedback resistance is:

$$R_f = \frac{U}{I} = \frac{10\text{ V}}{50\text{ }\mu\text{A}} = 200\text{ k}\Omega$$

To maintain high dynamic range without complex dynamic range switching, the feedback resistance is fixed at **$R_f = 200\text{ k}\Omega$**.

### Stability Equations
The photodiode's terminal capacitance ($C_d$) creates a pole with the feedback resistor ($R_f$) that erodes phase margin and causes gain peaking/ringing if left uncompensated. A feedback capacitor ($C_f$) in parallel with $R_f$ restores phase margin.

The standard TIA design equations are:

$$f_{-3\text{dB}} \approx \sqrt{\frac{\text{GBW}}{2\pi \cdot R_f \cdot C_d}}$$

$$C_f \approx \frac{1}{2\pi \cdot R_f \cdot f_{-3\text{dB}}} \approx \sqrt{\frac{C_d}{2\pi \cdot R_f \cdot \text{GBW}}}$$

---

## 2. Architectural Options

### Option A: Single-Stage High-Voltage TIA

A single transimpedance stage converts photocurrent directly into a $\pm 10\text{ V}$ signal driving the ADC.

```
                  +---| Rf (200 kΩ) |---+
                  |                     |
                  +---| Cf (~1.3 pF)|---+
                  |                     |
[ Photodiode ] -> (- Inverting )        |
                  (            ) [ Op-Amp ] ----> [ Low-Pass Filter ] -> [ ADC (±10V) ]
     ( Ground ) -> (+ Non-Invert)
```

#### Key Requirements:
- **Gain-Bandwidth Product (GBW):** Minimum **$5.3\text{ MHz}$** to hit 300 kHz bandwidth with $R_f = 200\text{ k}\Omega$ and $C_d = 47\text{ pF}$.
- **Input Bias Current ($I_b$):** Must be ultra-low (FET/CMOS input, $\le 10\text{ pA}$) to prevent significant DC offset errors across $200\text{ k}\Omega$.
- **Power Supply Rails:** Must support $\pm 15\text{ V}$ or $\pm 12\text{ V}$ to deliver full $\pm 10\text{ V}$ output to the ADC.

#### Suitable Op-Amp Candidates:
- **ADA4622-1:** JFET input, $\text{GBW} = 8\text{ MHz}$, $I_b = 10\text{ pA}$, $\pm 15\text{ V}$ supplies.
- **ADA4637-1:** High-speed JFET, $\text{GBW} = 79\text{ MHz}$, $I_b = 1\text{ pA}$, $\pm 15\text{ V}$ supplies.

---

### Option B: Two-Stage Architecture (OPA657 + AD797)

A hybrid approach decoupling the ultra-low noise, high-speed current conversion stage from the high-voltage voltage gain stage.

```
=== STAGE 1: TIA Stage (±5V Supply) ===       === STAGE 2: Voltage Gain Stage (±15V Supply) ===

                  +--| Rf1 (50 kΩ) |--+                                 +--| Rf2 (3 kΩ) |--+
                  |                   |                                 |                  |
                  +--| Cf1 (4.3 pF) |-+                                 +--| Rg2 (1 kΩ) |--+
                  |                   |                                                    |
[ Photodiode ] -> (- Inv )            |                                  (- Inv )          |
                  ( OPA657 ) ---------+-----> [ AC/DC Coupling ] ------> ( AD797 ) --------+--> [ ADC (±10V) ]
     ( Ground ) -> (+ Non-Inv )                                          (+ Non-Inv )
                                                                              |
                                                                          ( Ground )
```

#### Stage 1: Current-to-Voltage (OPA657)
- **Role:** High-speed TIA operating on low-voltage rails ($\pm 5\text{ V}$).
- **Performance:** JFET inputs ($I_b \approx 2\text{ pA}$), ultra-high bandwidth ($\text{GBW} = 1.6\text{ GHz}$), ultra-low voltage noise ($4.8\text{ nV}/\sqrt{\text{Hz}}$).
- **Stability Note:** The OPA657 is a *decompensated* op-amp stable only for high-frequency noise gain $\ge 7$. With $C_d = 47\text{ pF}$ and $C_f \approx 4.3\text{ pF}$, the high-frequency noise gain is:
  $$\text{Noise Gain}_{\infty} = 1 + \frac{C_d}{C_f} = 1 + \frac{47\text{ pF}}{4.3\text{ pF}} \approx 11.9$$
  Since $11.9 > 7$, Stage 1 is inherently stable.

#### Stage 2: Voltage Gain & Level Shifting (AD797)
- **Role:** Voltage amplifier running on $\pm 15\text{ V}$ rails to scale the Stage 1 output to match the ADC's $\pm 10\text{ V}$ range.
- **Performance:** Driven by the low-impedance output of Stage 1, erasing input bias current limitations ($250\text{ nA}$) while delivering ultra-low noise ($0.9\text{ nV}/\sqrt{\text{Hz}}$).

#### Power Supply Infrastructure:
- Requires dedicated **linear voltage regulators (LDOs)** (e.g., ADP7118 / ADP7182 or 78L05 / 79L05) to generate clean $\pm 5\text{ V}$ rails from the main $\pm 15\text{ V}$ supplies. *Resistor voltage dividers cannot be used for powering the OPA657 due to dynamic current draw variations.*

---

## 3. Comparison Matrix

| Feature / Metric | Option A: Single-Stage (e.g. ADA4622) | Option B: Two-Stage (OPA657 + AD797) |
|---|---|---|
| **Circuit Complexity** | Low (Single IC, simple layout) | Medium-High (2 ICs, LDO regulators) |
| **Supply Rails** | Single dual-rail pair ($\pm 15\text{ V}$) | Dual rail pairs ($\pm 5\text{ V}$ LDOs & $\pm 15\text{ V}$) |
| **Noise Performance** | Good (limited by single-stage trade-offs) | Superior (ultra-low noise OPA657 front-end) |
| **Bandwidth Headroom** | Moderate (8–79 MHz GBW) | Exceptional (1.6 GHz GBW front-end) |
| **PCB Footprint** | Small | Moderate |

---

## 4. Downstream Filtering & Protection

- **Anti-Aliasing Filter:** A single-pole RC low-pass filter ($f_c \approx 500\text{ kHz} - 1\text{ MHz}$) follows the TIA before the ADC to restrict out-of-band noise without distorting 300 kHz signals.
- **ADC Protection:** The DAQ system's ADC input natively tolerates overvoltage up to **$\pm 25\text{ V}$**. Because the maximum output from an AD797 or single $\pm 15\text{ V}$ stage is $\approx \pm 13.5\text{ V}$, **no protective clamping diodes are required**, preventing parasitic diode capacitance from degrading high-frequency signal integrity.

---

## 5. Critical PCB Layout Guidelines

1. **Summing Node Isolation:** Keep $R_f$, $C_f$, and photodiode trace lengths as short as physically possible, routing directly to the op-amp inverting pin.
2. **Ground Plane Clearance:** Cut away (void) the internal ground and power plane copper directly underneath the inverting input pin, photodiode anode pad, and feedback traces to eliminate parasitic capacitance loading the input.
3. **Guard Ringing:** Surround the inverting node with a grounded guard trace driven near the same potential to prevent surface leakage currents across high-resistance feedback paths.
4. **Supply Separation:** Keep the **48 V** photodiode reverse-bias line isolated and well-filtered from sensitive analog signal traces to prevent power supply ripple from coupling into the summing node.