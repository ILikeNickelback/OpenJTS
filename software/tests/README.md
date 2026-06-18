# Testing strategy

Tests live under `software/tests/` and run via `pixi run test` (equivalent to
`pytest software/tests`). Imports resolve the same way they do for the real
app (`pixi run python software/src/main.py`): `software/src` is on
`sys.path` via the `pythonpath` setting in the root `pyproject.toml`, so
modules are imported as `config.config`, `core.event_bus`, etc. — no `src.`
prefix.

## The three tiers

**`unit/`** — fully isolated, no hardware, no GUI, no real I/O. These cover
the modules in `software/src` that are pure logic: `sequence_builders/decoder.py`,
`sequence_builders/control.py`, `utils/data_processing.py`,
`core/workspace_manager.py`, and the parsing/preview path of
`sequence_builders/sequence_waveform_builder.py` (`SequencePreviewBuilder` and
the parsing helpers it shares with `SequenceWaveformBuilder`). Run with:

```
pytest -m unit
```

**`integration/`** — real components wired together through their actual
interfaces (constructors, command queues, public methods), with only the
hardware boundary faked:
- `test_esp32_port_discovery.py` fakes `serial.tools.list_ports.comports()`
  to test `Esp32Base`'s port-matching and its graceful no-hardware fallback.
- `test_worker_hardware_boundary.py` drives `AcquisitionBaseWorker`'s full
  command-queue lifecycle (`configure` → `start` → acquisition steps →
  `stop`/finish) against a hand-written `FakeADC` double (see `conftest.py`)
  instead of a real `mcculw`-backed ADC.

Run with:

```
pytest -m integration
```

`test_worker_hardware_boundary.py` is the template to copy when adding
similar coverage for `SequenceAcquisitionWorker` / `FrequencyAcquisitionWorker`,
or for the calibration/frequency waveform builders and `adc_base`'s voltage
conversion helpers — none of those are covered yet.

**`system/`** — full app smoke tests (real DearPyGUI viewport, real DAQ/ESP32
hardware). Not implemented or run automatically: DearPyGUI needs a live
viewport and the DAQ board/ESP32 need to be physically connected, neither of
which a GitHub-hosted runner can provide. For now this tier stays a manual
bench checklist before releases. Revisit if a self-hosted Windows runner with
an active display session becomes available.

## Markers

`unit`, `integration`, and `system` are registered in `pyproject.toml` so
`pytest -m <marker>` works without warnings. CI runs `pixi run test`, which
covers `unit` and `integration` (there are no `system` tests to collect yet).
