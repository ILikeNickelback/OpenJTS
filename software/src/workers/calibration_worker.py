"""Acquisition worker for the detection-LED calibration loop."""

from __future__ import annotations

import queue

import numpy as np

from config.config import config
from workers.base_worker import AcquisitionBaseWorker
from hardware.adc_calibration import CalibrationAcquisitionADC



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
                    if self.adc and hasattr(self.adc, "update_detection_intensity"):
                        try:
                            self.adc.update_detection_intensity(self.detection_intensity)
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

        self.experiment_type = config["General"].get("experiment_type")

        self.adc = CalibrationAcquisitionADC()
        self._owns_adc = True
        self.adc.configure()
        self.adc.start_reader()
        self.adc.start_calibration_using_adc(intensity=self.detection_intensity)

    def _stop_acquisition(self) -> None:
        """Stop AO waveform output first, then stop the AI scan."""
        self.acquiring = False
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
        delta_meas = np.mean(flash[:5]) - np.mean(pre[:5])
        delta_ref  = np.mean(flash[6:7]) - np.mean(pre[6:7])
        
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

        self.result_queue.put({
            "type": "live",
            "di":  _scalar(di_arr),
            "ref": _scalar(ref_arr),
        })
