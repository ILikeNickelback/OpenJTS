# Usage

This page explains how to install and start the OpenJTS software, run a measurement, and save your results.

---

## Before you start

You need:

- A Windows 10/11 (64-bit) PC
- The MCC DAQ board, connected by USB, with the MCC driver (InstaCal / Universal Library) installed
- The ESP32 controller, connected by USB and flashed with the OpenJTS firmware (see [Firmware](../firmware/firmware.md))
- [pixi](https://pixi.sh), used to install Python and all dependencies

---

## Installation

Install pixi (PowerShell):

```powershell
iwr -useb https://pixi.sh/install.ps1 | iex
```

Clone the repository and install the environment:

```powershell
git clone https://github.com/ILikeNickelback/OpenJTS.git
cd OpenJTS
pixi install
```

`pixi install` creates a local environment with the exact versions listed in `pixi.lock`. You only need to do this once, and again after pulling changes that modify `pixi.toml`.

---

## Starting the software

From the repository folder:

```powershell
pixi run python software/src/main.py
```

The application opens maximised. Connect the DAQ board and ESP32 **before** starting: the software looks for them at startup.

---

## The Home tab

The **Home** tab shows:

- **Device status**: whether the ADC (DAQ board) and the ESP32 are connected. If a device was plugged in after startup, or was not found, click **Retry** next to it.
- **Experiments**: a table of all the experiments open in this session, with their type.

The ESP32 is found automatically by looking for a serial port whose description contains "USB" or "UART". If other USB-serial devices are plugged in, the software might pick the wrong one. Unplug them if the ESP32 is not detected.

---

## Creating an experiment

Click the **+** button at the end of the tab bar. In the dialog:

1. Enter an **experiment name** (for example `Run 01`).
2. Choose **Fluo** (fluorescence) or **Spectro** (spectroscopy).
3. Choose the acquisition type:
   - **Sequence**: you describe the light pulses with a sequence string (see [Sequence language](sequence-language.md)).
   - **Frequency**: the actinic light is modulated as a sine wave and detection pulses are spread evenly over each period.
4. Click **Create**.

You can open several experiments at once. Each one has its own tab, settings and results.

Each experiment tab has four sub-tabs:

| Sub-tab | Contents |
|---|---|
| **Overview** | Experiment metadata (sample, notes, …) and the sequence history log |
| **Setup** | Sequence or frequency editor, detection LED, actinic light, data processing settings, preview plot, sequence library |
| **Acquisition** | Live plot, sample container, Start/Stop controls |
| **Post-processing** | Not implemented yet |

---

## Setting up a sequence experiment

All of this happens in the **Setup** sub-tab.

### 1. Write or load a sequence

Type a sequence string in the **Sequence input** box, for example:

```
4(100msD) A[100] 50ms A[0] 300µsD 1msD 2msD 5(5msD) 5(10msD)
```

The syntax is described in [Sequence language](sequence-language.md).

- **+ Add** adds another sequence. Sequences are run one after the other.
- **Delete** removes a sequence.
- **Visualize** draws the sequence in the preview plot. Check the timing here before you measure.
- **Parameters** opens the data processing settings for that sequence (see below).

To reuse a saved protocol (ECS, Phi PSII, …), open the **Load Experiment** panel (the sequence library) and add an entry to the experiment. **View** previews it, and **+ New** saves the current sequence to the library. The library is stored in `software/src/config/sequences.json`.

### 2. Set the data processing parameters

The **Data Processing** panel has these settings for each sequence:

| Setting | Effect |
|---|---|
| **Baseline points** | The mean of the first N points is subtracted from every point. `0` turns this off. |
| **Number of averages** | The sequence is run this many times and the results are averaged. |
| **Time between averages** | Wait time (ms) between two runs of the same sequence. |
| **Sequences to ignore** | Number of warm-up runs done first and thrown away (not averaged). |
| **Time before next sequence** | Wait time (ms) before moving on to the next sequence. |

The total number of runs for a sequence is *sequences to ignore + number of averages*.

### 3. Set the lights

- **Detection LED**: sets the detection LED intensity (%). **Start flash (1 Hz)** fires the detection LED continuously so you can check and adjust the signal before measuring.
- **Actinic Light**: sets a constant background actinic light (%). **Turn ON** applies it.

### 4. Load the sequences

Click **Load sequence** in the **Sequence Handler**. This checks the hardware, decodes all sequences, and shows the **total number of runs** and the **estimated total time**. The status shows "Ready" when everything is loaded.

If the status shows "ADC not connected", go back to the Home tab and click **Retry**.

---

## Setting up a frequency experiment

In a **Frequency** experiment, the Setup sub-tab shows **Frequency Settings** instead of a sequence editor:

| Field | Meaning |
|---|---|
| **Frequency** | Actinic light modulation frequency (Hz) |
| **Amplitude** | Sine amplitude (% of full scale) |
| **Offset** | Sine DC offset (% of full scale) |
| **Number of periods** | Number of modulated periods |
| **Pre / post detection** | Number of unmodulated periods measured before and after the sine |

Saturating pulses can be added at a chosen period and phase (degrees) in the **Saturating Pulse** panel. Configurations can be saved and reloaded with **Save frequency config** and **Load frequency config**. Click **Load sequences** in the **Frequency Handler** before starting.

---

## Running the acquisition

Go to the **Acquisition** sub-tab and click **Start**.

- The **live plot** updates while each run is acquired.
- The counter shows the current phase ("Ignoring…", "Averaging: run 2/5", …) and the progress bar shows how far through the run you are.
- When all averages of a sequence are done, the averaged curve is added to the **Sample Container**, and the next sequence starts.

Click **Stop** to abort. The ESP32 stops at its next delay, and the actinic light goes back to its background level.

---

## Saving results

### Exporting samples

In the **Sample Container**, each finished result is a sample. You can rename it, tick it, or right-click it to delete it. **Save selected samples** writes the ticked samples to a JSON file:

```json
{
    "Sample name": {
        "sequence": "...",
        "time": [0.0, 100.02, 200.04],
        "values": [0.0012, 0.0010, 0.0011]
    }
}
```

`time` is in milliseconds from the start of the sequence, and `values` are the measured points (ΔI/I), after baseline subtraction and averaging.

### Saving the workspace

The **File** menu saves the whole session (all experiments, their sequences, parameters, metadata and results):

- **Save As** asks for a folder and a name, and creates a workspace folder containing `workspace.json` and one `<experiment name>.json` file per experiment.
- **Save** writes to the same workspace folder again.
- **Open Workspace** reloads a session from its `workspace.json` file.

### Autosave

After every finished acquisition, a snapshot of the experiment is written to `software/src/temp/autosave.json`. It is overwritten each time, so copy it elsewhere if you need to recover data after a crash.

---

## Configuration

General settings are in `software/src/config/config.json`. The ones you are most likely to change:

| Key | Meaning |
|---|---|
| `General.hardware` | `"ESP32"`: the ESP32 plays sequences and drives the LEDs, and the DAQ only records. `"ADC"`: the DAQ board generates the light waveforms itself. |
| `General.fontsize` | UI font size |
| `ADC.board_num` | MCC board number (as set in InstaCal) |
| `ADC.sampling_rate` | Input sampling rate (Hz) |
| `ESP32.baud_rate` | Must match the firmware (`115200`) |
| `LED.actinic_light_offset`, `LED.detection_light_offset` | DAC offsets to compensate for LED non-linearity |
| `Debug.enabled` | Turns on verbose logging |

Restart the software after editing this file.

---

## Logs

**Tools → Show Logs** opens the log window. Check it first when something does not behave as expected: hardware errors, decoding problems and autosave failures are reported there.
