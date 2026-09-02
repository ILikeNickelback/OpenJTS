# Full build manual

This presents the full step-by-step instructions to build an OpenJTS. You will first need to order the materials indicated in the [Bill of Materials](bom.md).

Before you start:

- Read through the [Technical notes](../technical-notes/index.md) for the module you are working on — they explain *why* each part is built the way it is, which makes it much easier to spot a mistake during assembly.
- Gather the tools listed at the bottom of the [BOM](bom.md): soldering iron, screwdrivers and spanners, pliers, and a small drill.
- Work on the electronics (preamp PCBs, LED controller, front panel PCB) on an ESD-safe surface. The AD797 and JFET op-amps used in the preamps are sensitive to static discharge.
- The instrument uses a 48 V rail to reverse-bias the photodiodes and drive the detection LEDs. Treat it with the same care as any other line-powered voltage: power down the supplies before touching exposed connections.

*Add photo here*

---

## Assembling the structure

The mechanical structure is built from 25 mm square optical construction rails (Thorlabs XE25 series), joined with construction cubes and elbow plates, and finished with drop-in T-nuts and low-profile channel screws. This rail frame carries the two preamp cases and the LED housings.

1. Cut or order the rails to the lengths required for your layout, and fit the frame using the construction cubes (corners) and elbow plates (right-angle joints).

*Add photo here*

---

## Building the cables

Three families of cable are needed:

- **Coax (BNC) cables** — carry the preamp outputs to the ADC's analog inputs and trigger the laser. Build 4, per the [BOM](bom.md).
- **Sub-D9 cables** — carry power and control signals between the instrument case and the preamp/LED modules.

1. Cut each cable to desired length so runs are neither too tight nor excessively long.
2. Solder or crimp the connectors specified in the [BOM](bom.md) (Sub-D9 male/female, coax connectors) onto each cable. Be carefull to solder the rigth Sub-D9 pins to the righ place.
3. Label both ends of every cable as you build it — with two symmetric channels (measurement/reference) and two LED paths, it is easy to mix up otherwise.

*Add photo here*

---

## Assembling the preamp cases

Each detection channel (measurement and reference) has its own preamp case, so this section is carried out **twice**. The case houses the transimpedance amplifier (TIA) that turns the photodiode's photocurrent into a voltage — see [Transimpedance Amplifier Design](../technical-notes/preamp-design.md) for the full rationale behind the component choices below.

1. Populate the Preamp PCB (JLCPCB order from the [BOM](bom.md)) with the AD797 op-amp(s), feedback resistor/capacitor network, and supporting components as described in [Transimpedance Amplifier Design](../technical-notes/preamp-design.md). 

Note: it is also possible to order the PB fully populated but this will be more expensive and won't be simple to repair if a component fries.

*Add photo here*

2. Place the photodiode on the photodiode holder and solder to the Preamp PCB. Keep the wires as short as possible.

3. Screw the Sub-D9 right angle connector to the preamp case.

4. Close and screw the photodiode holder and preamp case base. 

5. Insert the long M6 srew in the appropriate hole and screw it to the Thorlabs T-nut.

6. Place on structure

*Add photo here*

---

## Assembling the LED cases

The instrument uses two independent light paths: the **detection** LEDs (short, stable flashes used to probe the sample) and the **actinic** LED (the light that drives the physiological change being observed). See [Technical choices: LED control](../technical-notes/LED-control.md) for why each was designed the way it was.

### Detection LED assembly (×2, one per channel)

1. Mount the detection LED onto the **Detection holder**.
2. Solder the Detection LED Sub-D9 power cabler to the the LED. Beware of the posisitve and negative side.

### Actinic LED assembly

1. Populate the **Actinic LED PCB** with the LED array as specified in [LED control](../technical-notes/LED-control.md). Note: if you have access to a SMD oven this is great. 
2. Mount the LED PCB onto the **Actinic holder**(s). 
3. Solder the Actinic LED Sub-D9 power cabler to the the LED PCB. Beware of the posisitve and negative side.

*Add photo here*

*Add photo here*

## Mount the cases

1. Glue the diffuseur to the diffeuseur stage.
2. assemble all 3 stages together with appropriate screws.
3. Insert the long M6 srew in the appropriate hole and screw it to the Thorlabs T-nut.
4. Place on structure.

---

## Building common ground circuit
1. Add cable inserts (the green things that you can screw)

## Installing the power supplies

Three supplies are used:

| Supply | Used for |
|---|---|
| 15 V linear | ±15 V analog rails for the preamp op-amps and the actinic VCCS (see [VCCS Design](../technical-notes/VCCS-design.md)) |
| 15 V switching | Power for actinic LED|
| 48 V switching | Photodiode reverse bias and detection LED driver (see [LED control §1.2](../technical-notes/LED-control.md#12-intensity)) |

1. Mount all three supplies inside the instrument case on standoffs.
2. Wire the inputs of all 3 supplies to the same power line filter.
3. Wire the +15v to a crimp and the 0 to common ground
4. Wire the +48v to a crimp and the 0v  to a crimp
5. Wire the +15v and -15v to a crimp and the 0v to common ground 
*Add photo here*

---

## Installing the front panel PCB

The front panel carries the instrument's external Sub-D9 connectors.

1. Mount the **Front panel** CNC plate onto the front face of the instrument case.
2. Fit the Sub-D9 male/female connectors into their cutouts, referring to the [BOM](bom.md) for connector counts.
3. Populate and mount the Front panel PCB behind the plate, and connect it to the panel connectors.

*Add photo here*

---

## Wire the ADC analog inputs



## Installing the LED controler and ADC

### TODO 
- The **LED controller PCB** is the VCCS (voltage-controlled current source) and MOSFET board that drives the actinic and detections LEDs from an analog or digital output (ADC or esp32) : see [VCCS Design](../technical-notes/VCCS-design.md) for the full circuit (IRF540N MOSFET, AD797 op-amp, 30 Ω sense resistor, voltage divider on the input).
- The **ADC** is the MCC USB-1808X DAQ board, which generates the actinic/detection waveforms and digitises the preamp outputs — see [Waveform Generation](../technical-notes/waveform-generation.md) for how its three output channels (2 analog + 1 digital trigger) are used.

1. Populate the LED controler PCB with the right components.
2. .....
3. Mount the MCC USB-1808X in the instrument case (or externally, per its enclosure) and connect its USB link to the host PC.
4. Leave the ADC's analog inputs, AO1 (detection flash), and digital trigger port unconnected for now — these are wired up in [Connecting the cables](#connecting-the-cables).
1. Mount the LED controller PCB inside the instrument case in the right position according to the front panel.

*Add photo here*

---

## Installing the esp32

The ESP32 is a secondary controller used for one-shot commands and standalone sequencing (including laser triggering, which the ADC path cannot do — see [Waveform Generation §2](../technical-notes/waveform-generation.md#2-esp32-many-digital-pins-two-8-bit-dacs)). Pin assignments are documented in [Firmware](../../firmware/firmware.md).

1. Seat the ESP32 dev board onto its support board.
2. Mount the assembly inside the instrument case accordint to the front panel holes
3. TODO: wire the cables.
3. Connect the ESP32's USB port to the host PC (or to an internal hub if the instrument exposes a single external USB port).

*Add photo here*

---



## Building Molex connectors

Power distribution inside the instrument case uses Molex KK 396 8-way connectors (male header + female housing) with crimp terminals.

1. Strip a few millimetres of insulation from each wire.
2. Insert the wire into a crimp terminal and crimp it with the crimping tool, checking for a firm mechanical and electrical connection (a light tug test).
3. Insert each crimped terminal into its position in the Molex female housing until it clicks into place, following a consistent pin-out across every harness you build.
4. Solder or mount the matching male header onto the receiving PCB or terminal block.

*Add photo here*

---

## Connecting the cables

### TODO: correct the things 

With all cables installed, make the final connections:

| From | To | Notes |
|---|---|---|
| Preamp PCB output (×2) | ADC analog input (BNC) | Measurement and reference channels |
| ADC AO0 | LED controller (VCCS) input | Actinic level, see [Waveform generation §1.4](../technical-notes/waveform-generation.md#14-channel-0--actinic-light) |
| LED controller output | Actinic LED PCB | See [VCCS design](../technical-notes/VCCS-design.md) |
| ADC AO1 | Detection LED driver | Detection flash amplitude, see [Waveform generation §1.5](../technical-notes/waveform-generation.md#15-channel-1--detection-flash) |
| ADC digital port | Acquisition trigger | See [Waveform generation §1.6](../technical-notes/waveform-generation.md#16-channel-2--the-trigger) |
| ESP32 `actinicDacPin` (GPIO26) | Actinic driver (standalone/manual mode) | See [Firmware](../../firmware/firmware.md#hardware-pins) |
| ESP32 `detectorDacPin` (GPIO25) | Detection LED driver (standalone/manual mode) | Digital on/off only |
| ESP32 `TriggPin` (GPIO12) | External DAQ trigger (optional) | |
| ESP32 `laserChannel_open` / `laserChannel_start` (GPIO18/19) | External laser controller (optional) | Only available on the ESP32 path |
| Power supplies | Molex power harness | Distribute ±15 V, 48 V, and ground to the preamp PCBs, LED controller, and front panel |

1. Connect the Molex power harness first, and check rail voltages at each board's power input **before** connecting any signal cable.
2. Connect the BNC signal cables from each preamp to the ADC.
3. Connect the actinic and detection drive cables from the ADC/LED controller to the LED PCBs.
4. Connect the ESP32 control lines.
5. Power on the instrument and confirm, with the host software, that both detection channels read a stable baseline and that the actinic and detection LEDs respond to test commands before running any real sequence.

*Add photo here*
