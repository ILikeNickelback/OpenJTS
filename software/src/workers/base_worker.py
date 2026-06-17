"""Base acquisition worker thread shared by all experiment types."""

#TODO fix AUTOSAVE because it crashes sometimes


from __future__ import annotations

import json
import os
import threading
import queue
import time
from datetime import datetime
from typing import Optional
import numpy as np

from hardware.adc_base import ADCBase

_BRUT_DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "temp"))
 
 
class AcquisitionBaseWorker(threading.Thread):
    """Base worker thread that drives the acquisition loop.
 
    Responsibilities:
    - command queue dispatch (configure / start / stop / shutdown)
    - acquisition step loop (read one block → process → publish result)
    - hardware lifecycle (owns ADC if it created it)
 
    Subclasses override:
    - init_adc()           -- create and configure the concrete ADC object
    - prepare_time_values() -- populate self.time_values (or leave None)
    - process_block()      -- convert a raw block to a scalar measurement
    """
 
    def __init__(self, adc: Optional[ADCBase] = None, esp32=None):
        """Initialise the worker thread.

        Args:
            adc: Pre-constructed ADC instance to reuse. If None, the subclass
                `init_adc()` will create one and set `_owns_adc = True`.
            esp32: Optional ESP32 handle passed through to subclasses.
        """
        super().__init__(daemon=True)
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()

        self.adc: Optional[ADCBase] = adc
        self.esp32 = esp32

        self.running = True
        self.acquiring = False
        self._owns_adc = False
        self.force_stop = threading.Event()

        # Set by "configure" command before "start"
        self.sequence = None
        self.nbr_of_points = None
        self.config = {}
        self.experiment_type = None
        self.tab_name: str = "experiment"
        self._brut_run_key: str = ""
        self._brut_data_buffer: dict = {}
        self.time_values = None
        self.current_point = 0
        self.final_values = []

    # ---------------------------
    # GUI API
    # ---------------------------
    def send_command(self, cmd: dict) -> None:
        """Enqueue a command dict to be processed by the worker thread.

        Args:
            cmd: Dict with at minimum an ``"action"`` key.
        """
        self.command_queue.put(cmd)
 
    # ---------------------------
    # Thread loop
    # ---------------------------
    def run(self) -> None:
        """Main thread loop: dispatch commands and execute acquisition steps."""
        try:
            while self.running and not self.force_stop.is_set():
                self._process_pending_commands()
                if self.acquiring:
                    self._execute_acquisition_step()
                time.sleep(0.001)
        finally:
            if self._owns_adc and self.adc and hasattr(self.adc, "shutdown"):
                self.adc.shutdown()
 
    def shutdown_forcefully(self) -> None:
        """Force the thread to stop even if the command queue is blocked."""
        self.force_stop.set()
 
    # ---------------------------
    # Command dispatch
    # ---------------------------
    def _process_pending_commands(self) -> None:
        """Drain the command queue and act on each command.

        Handles: ``configure``, ``start``, ``stop``, ``shutdown``.
        Subclasses may override to handle additional actions.
        """
        try:
            while True:
                cmd = self.command_queue.get_nowait()
                action = cmd.get("action")

                if action == "configure":
                    self.sequence = cmd["sequence"]
                    self.nbr_of_points = cmd.get("nbr_of_points")
                    self.config = cmd.get("config") or {}
                    self.experiment_type = cmd.get("experiment_type")
                    self.tab_name = cmd.get("tab_name", "experiment")

                elif action == "start":
                    self._start_acquisition()

                elif action == "stop":
                    self._stop_acquisition()

                elif action == "shutdown":
                    self.running = False
                    self.acquiring = False
                    return
 
        except queue.Empty:
            pass
 
    # ---------------------------
    # Acquisition flow
    # ---------------------------
    def _start_acquisition(self) -> None:
        """Reset counters, initialise the ADC, and begin acquiring."""
        self.acquiring = True
        self.current_point = 0
        self.final_values = []
        self._brut_data_buffer = {}
        self._brut_run_key = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.init_adc()
        self.prepare_time_values()
 
 
    def _stop_acquisition(self) -> None:
        """Flush buffered data and stop the ADC scan."""
        self.acquiring = False
        self._flush_brut_data()
        if self.adc:
            if hasattr(self.adc, "stop_acquisition"):
                self.adc.stop_acquisition()
            if hasattr(self.adc, "stop_reader"):
                self.adc.stop_reader()
 
    # ---------------------------
    # Acquisition step
    # ---------------------------
    def _execute_acquisition_step(self) -> None:
        """Read one block from the ADC and route it for processing."""
        if self.nbr_of_points and self.current_point >= self.nbr_of_points:
            self._finish_acquisition()
            return
 
        raw_block = self._read_one_point_from_adc()
        if raw_block is None:
            return
 
        self._handle_block(raw_block)
 
    def _finish_acquisition(self) -> None:
        """Stop the ADC and publish the final result to ``result_queue``."""
        self.acquiring = False
        self._stop_acquisition()
        self.result_queue.put({
            "type": "final",
            "final_results": self.final_values,
            "time_values": self.time_values,
            "sequence": self.sequence,
        })
        bg = self.config.get("background_light_data")
        if self.adc and bg is not None:
            self.adc.set_background_light(float(bg))
 
    def _handle_block(self, raw_block) -> None:
        """Route a raw block to live/calibration or normal acquisition handling."""
        y = self.process_block(raw_block)
        x = self.time_values[self.current_point] if (self.time_values and self.current_point < len(self.time_values)) else self.current_point
        self.result_queue.put({"type": "live", "y": y, "x": x})

        if self.nbr_of_points:
            self.result_queue.put({
                "type": "progress",
                "progress": self.current_point / self.nbr_of_points,
            })

        self.final_values.append(y)
        self.current_point += 1
 
    # ---------------------------
    # Hardware read
    # ---------------------------
    def _read_one_point_from_adc(self):
        """Return one raw block from the ADC, or None if not enough samples are ready.

        Returns:
            Raw block data, or None if the ADC buffer is not yet full.
        """
        block_size = self.adc.samples_per_trigger * self.adc.nbr_of_triggers_per_sample
        if self.adc.get_status() < block_size:
            return None
        return self.adc.read_block()

    # ---------------------------
    # Brut data persistence (frequency mode only)
    # ---------------------------
    def _buffer_brut_data(self, v: np.ndarray, point_index: int) -> None:
        """Stage raw voltage array for the current point in the in-memory buffer.

        Args:
            v: Raw voltage array for this acquisition point.
            point_index: Index of the current acquisition point.
        """
        self._brut_data_buffer[str(point_index)] = v.tolist()

    def _flush_brut_data(self) -> None:
        """Write the in-memory raw-data buffer to disk and clear it."""
        if not self._brut_data_buffer:
            return
        path = os.path.join(_BRUT_DATA_DIR, f"brut_data_{self.tab_name}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        data.setdefault(self.tab_name, {})[self._brut_run_key] = {
            "settings": self.config.get("frequency_config", {}),
            "data": self._brut_data_buffer,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._brut_data_buffer = {}

    # ---------------------------
    # Signal processing (subclass may override)
    # ---------------------------
    def process_block(self, raw_block):
        """Convert a raw ADC block to a scalar measurement value.

        Handles both 2-trigger (sequence) and multi-trigger (frequency) modes,
        and both ``Spectro`` and non-spectro experiment types.

        Args:
            raw_block: Raw integer samples from ``adc.read_block()``.

        Returns:
            float: Processed measurement in µV units.
        """
        voltages = np.array([self.adc.to_voltage_32(v) for v in raw_block])
        # Each row = one trigger acquisition across all 8 channels
        v = voltages.reshape(-1, 8)
        meas = v[:, :4]   # channels 0-5: measurement
        ref  = v[:, 4:]   # channels 6-7: reference
        # print(v)
        if self.adc.nbr_of_triggers_per_sample == 2:
            # Sequence mode: trigger 0 = pre-flash, trigger 1 = during-flash
            pre, flash = v[0], v[1]
            delta_meas = np.mean(flash[:4]) - np.mean(pre[:4])
            delta_ref  = np.mean(flash[6:7]) - np.mean(pre[6:7])
            # print(delta_meas)
            self._buffer_brut_data(v, self.current_point)
            if self.experiment_type == "Spectro":
                result = np.round((-delta_meas) / delta_ref, 7) * 1e6
                return result
            else:
                return np.round(delta_meas, 7) * 1e6
            
    
        else:
            # Frequency mode: triggers 0..n-1 = pre-flash, trigger n = during-flash
            n = self.adc.nbr_of_triggers_per_sample - 1   # = points_before_flash
            pre_meas   = np.mean(meas[:n], axis=1)         # (n,) one value per pre-trigger
            pre_ref    = np.mean(ref[:n],  axis=1)         # (n,)

            flash_meas = np.mean(meas[n])                  # scalar
            flash_ref  = np.mean(ref[n])                   # scalar

            self._buffer_brut_data(v, self.current_point)

            if self.experiment_type == "Spectro":
                pre_ratio   = pre_meas / pre_ref          # (n,) ratio per pre-flash point
                pre_times   = np.array([0, 60, 120])
                flash_time  = 145
                slope, intercept = np.polyfit(pre_times, pre_ratio, 1)
                linear_regression = slope * flash_time + intercept
                flash_delta = flash_meas / flash_ref
                return np.round(flash_delta - linear_regression, 7) * 1e6
            else:
                pre_times = np.array([0, 60, 120])
                flash_time = 145
                slope, intercept = np.polyfit(pre_times, pre_meas, 1)
                linear_regression = slope * flash_time + intercept
                return np.round(flash_meas - linear_regression, 7) * 1e6
 
    # ---------------------------
    # Subclass hooks
    # ---------------------------
    def init_adc(self) -> None:
        """Create, configure, and arm the ADC. Must be overridden by every subclass."""
        raise NotImplementedError

    def prepare_time_values(self) -> None:
        """Generate index-based time values as a fallback (0 … nbr_of_points-1)."""
        if self.nbr_of_points:
            self.time_values = list(range(self.nbr_of_points))
        else:
            self.time_values = None

