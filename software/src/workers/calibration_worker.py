"""Acquisition worker for the detection-LED calibration loop."""

from __future__ import annotations

import queue

import numpy as np

from config.config import config
from workers.base_worker import AcquisitionBaseWorker
from hardware.adc_calibration import CalibrationAcquisitionADC
from hardware.adc_calibration_external import ExternalCalibrationAcquisitionADC


class CalibrationAcquisitionWorker(AcquisitionBaseWorker):
    """Worker for the detection-LED calibration loop.

    Differences from sequence/frequency workers:

    - Runs indefinitely (nbr_of_points=None) until manually stopped.
    - Uses its own command set: configure_calibration / start_calibration /
      stop_calibration / shutdown / set_detection_intensity.
    - _handle_block() emits {"type": "live", "di": float, "ref": float}
      so the calibration UI can display each channel independently.
    """

    def __init__(self, *args, **kwargs):
        """Initialise the calibration worker with default detection intensity.

        Args:
            *args: Passed to `AcquisitionBaseWorker.__init__`.
            **kwargs: Passed to `AcquisitionBaseWorker.__init__`.
        """
        super().__init__(*args, **kwargs)
        self.detection_intensity = 100.0
        self._hardware_mode = None
        self._discard_next_block = False

    # ------------------------------------------------------------------
    # Command dispatch — calibration-specific commands only
    # ------------------------------------------------------------------
    def _process_pending_commands(self) -> None:
        try:
            while True:
                cmd = self.command_queue.get_nowait()
                action = cmd.get("action")

                if action == "configure_calibration":
                    self.sequence = cmd.get("sequence")
                    if "intensity" in cmd:
                        self.detection_intensity = float(cmd["intensity"])

                elif action == "set_detection_intensity":
                    self.detection_intensity = float(cmd.get("intensity", 100.0))
                    if self._hardware_mode == "ESP32" and self.esp32:
                        self._send_esp32_intensity(self.detection_intensity)
                    elif self.adc and hasattr(self.adc, "update_detection_intensity"):
                        try:
                            self.adc.update_detection_intensity(
                                self.detection_intensity
                            )
                        except Exception:
                            pass

                elif action == "start_calibration":
                    self._start_acquisition()

                elif action == "stop_calibration":
                    self._stop_acquisition()

                elif action == "shutdown":
                    self.running = False
                    self.acquiring = False
                    return

        except queue.Empty:
            pass

    # ------------------------------------------------------------------
    # ADC lifecycle
    # ------------------------------------------------------------------
    def init_adc(self) -> None:
        """Shut down any existing ADC, then create and arm a new calibration ADC."""
        if self._owns_adc and self.adc and hasattr(self.adc, "shutdown"):
            self.adc.shutdown()

        # The first block captured right after the AI scan is newly armed is
        # unreliable (analog front-end hasn't settled) — drop it once.
        self._discard_next_block = True

        self.experiment_type = config["General"].get("experiment_type")
        self._hardware_mode = config["General"].get("hardware", "ADC")

        if self._hardware_mode == "ESP32":
            self.adc = ExternalCalibrationAcquisitionADC()
            self._owns_adc = True
            self.adc.configure()
            self.adc.start_reader()

            # Intensity must reach the ESP32 before the "#" start-flash command
            # — the firmware applies whatever intensity is current as of its
            # very first flash, with no chance to catch up afterward.
            self._send_esp32_intensity(self.detection_intensity)

            freq = float(config["ADC"].get("frequency", 1.0))
            interval_ms = max(1, round(1000.0 / freq)) if freq > 0 else 200
            self.esp32.send_sequence(f"#{interval_ms}")
        else:
            self.adc = CalibrationAcquisitionADC()
            self._owns_adc = True
            self.adc.configure()
            self.adc.start_reader()
            self.adc.start_calibration_using_adc(intensity=self.detection_intensity)

    def _send_esp32_intensity(self, intensity: float) -> None:
        """Send the detection LED intensity (0-100%) to the ESP32."""
        if self.esp32:
            self.esp32.send_sequence(f"S{intensity:.1f}")

    def _stop_acquisition(self) -> None:
        """Stop AO waveform output first, then stop the AI scan."""
        self.acquiring = False
        if self._hardware_mode == "ESP32" and self.esp32:
            self.esp32.send_sequence("@")
        if self.adc:
            if hasattr(self.adc, "stop_calibration_using_adc"):
                try:
                    self.adc.stop_calibration_using_adc()
                except Exception:
                    pass
            if hasattr(self.adc, "stop_acquisition"):
                self.adc.stop_acquisition()
            if hasattr(self.adc, "stop_reader"):
                self.adc.stop_reader()
        self.result_queue.put({"type": "progress", "progress": 0})

    def prepare_time_values(self) -> None:
        """No-op: calibration runs indefinitely with no fixed point count or time axis."""
        # Calibration runs indefinitely — no fixed point count or time axis.
        self.time_values = None
        self.nbr_of_points = None

    # ------------------------------------------------------------------
    # Block processing
    # ------------------------------------------------------------------
    def process_block(self, raw_block):
        """Return (reference_diff, measurement_diff) as numpy arrays."""
        voltages = np.array([self.adc.to_voltage_32(v) for v in raw_block])

        # Each row = one trigger acquisition across all 8 channels
        v = voltages.reshape(-1, 8)

        # Sequence mode: trigger 0 = pre-flash, trigger 1 = during-flash
        pre, flash = v[0], v[1]
        delta_meas = np.mean(flash[:3]) - np.mean(pre[:3])
        delta_ref = np.mean(flash[4:]) - np.mean(pre[4:])

        return delta_ref, delta_meas

    def _handle_block(self, raw_block) -> None:
        """Emit a live message with separate di (measurement) and ref channels."""

        ref_arr, di_arr = self.process_block(raw_block)

        def _scalar(arr):
            if arr is None:
                return 0.0
            try:
                return float(arr[0])
            except (TypeError, IndexError):
                return float(arr)

        self.result_queue.put(
            {
                "type": "live",
                "di": _scalar(di_arr),
                "ref": _scalar(ref_arr),
            }
        )
