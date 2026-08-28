# OpenJTS Software — Overview

## What It Is

OpenJTS is a desktop application (Python 3.14) for running experiments on the OpenJTS hardware. The user defines a sequence of light pulses and sees the results plotted in real time. It drives a specific DAQ board and can interact with an ESP32 over serial. The UI is built on the **DearPyGui (DPG)** library.

---

## Architecture

Launching `main.py` creates a DPG context and viewport, initializes the ADC and ESP32 instances, and starts the render loop, which updates the UI each frame in response to events.

The app is event-driven, built on two pillars:

- **AppState** — a single shared object holding all runtime data (experiments, sequences, parameters, hardware references). It is passed into every window at construction.
- **EventBus** — a publish/subscribe message broker. Windows never call each other directly; they publish named events with keyword arguments, and subscribers are invoked synchronously.

---

## Threading

OpenJTS makes heavy use of threads and queues, driven by one DPG constraint: item creation, deletion, and configuration must happen on the main DPG thread. Threads communicate by writing to queues that other threads can safely read.

There are four thread roles:

- **Main thread** — owns all DPG item creation, deletion, and configuration, the per-frame callback, and event dispatch.
- **Worker thread** — waits on a command queue and manages the acquisition: starts/stops it, launches the ADC reader thread, and turns raw data blocks into scalar points pushed to the result queue.
- **ADC reader thread** — polls the ADC every 1 ms, accumulating samples into a trigger block; when the block is full (one detection pulse) it pushes to the data queue.
- **Polling thread** — reads the result queue and applies statistical processing (averaging, baseline, etc.), then hands results to the main thread for plotting.

In short: the reader collects raw samples, the worker turns them into scalar data points, the polling thread does statistical processing and routing, and the main thread owns all rendering.

---

## Window Hierarchy

- **Main window** — top-level DPG primary window; hosts the menu bar (File, Tools) and the `TabbedWindowManager`.
- **Home window** — static tab showing device connection status and a table of all experiments with their metadata.
- **Experiment tab** — one experiment's content, with its own isolated `tab_bus` and a nested sub-tab bar.

---

## Acquisition Pipeline

The flow from user input to plotted results:

**Define → Load → Start → Acquire → Return → Display**

1. **Define** — the user types sequence strings (e.g. `4(100msD)A[100]20msA[0]300µsD`); multiple sequences are allowed.
2. **Load** — the decoder expands repeats and converts units into a token list stored in `AppState`, then publishes `sequence_list_ready`.
3. **Start** — resets the sequence index, records the start time, and dispatches `configure` + `start` commands to the worker.
4. **Acquire** — the worker reads blocks from the ADC, computes ΔI/I per block, and streams live points back through the result queue.
5. **Return** — the polling thread applies baseline subtraction and averaging, then routes finished results to the main thread through a thread-safe queue.
6. **Display** — the main thread drains that queue each frame and publishes to the UI, updating the plot and sample container.

> For the internals of any stage — decoding rules, the total-time formula, baseline/averaging logic, event names and payloads — see the inline comments and autodocs.