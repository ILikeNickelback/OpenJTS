import dearpygui.dearpygui as dpg
import threading
import queue
import time
import numpy as np

from core.window_base import WindowBase
from workers.sequence_worker import SequenceAcquisitionWorker
from workers.frequency_worker import FrequencyAcquisitionWorker


class Acquisition_win(WindowBase):
    """
    Acquisition control panel for multi-sequence or frequency runs.

    Manages a SequenceAcquisitionWorker or FrequencyAcquisitionWorker in a
    background thread, polls results, applies baseline subtraction, ignore
    runs, and per-sequence averaging, then publishes final data on the bus.
    DPG calls that originate from the polling thread are deferred through
    _main_thread_queue and drained each frame on the main thread.
    """

    def __init__(self,
                 label="Acquisition Control", pos=None, width=None, height=None,
                 uuid=None, visible=True,
                 state=None, bus=None):

        super().__init__(label=label, uuid=uuid, visible=visible)

        self.state = state
        self.bus = bus

        # --- per-run state ---
        self.sequence_list = []   # [{str_sequence, decoded, nbr_of_points}, ...]
        self.sequence_index = 0
        self.stop_requested = False
        self._run_start_time = None        # wall-clock time when the current HW run started
        self._experiment_start_time = None # wall-clock time when the full acquisition started

        # --- averaging / ignore state (reset per sequence) ---
        self._ignored_count = 0   # how many runs have been ignored for current seq
        self._avg_buf = []        # baseline-subtracted arrays collected so far
        self._current_params = {} # params active for the sequence being run

        # --- config kept from last input_cb call (applies to all sequences) ---
        _first_exp = self.state.get_experiments()[0]
        self.acquisition_type = _first_exp["experiment_type"]
        self.tab_name: str = _first_exp.get("name", "experiment")

        self.current_config = {}

        # --- worker / polling ---
        self.worker_thread = None
        self.polling_thread = None
        self.polling_thread_stop = threading.Event()
        self.polling_enabled = False

        # --- thread-safe queue for bus events that touch DPG (must run on main thread) ---
        self._main_thread_queue: queue.Queue = queue.Queue()

        self.pos = pos
        self.width = width
        self.height = height

        if self.bus:
            self.bus.subscribe("sequence_list_ready",       self._on_sequence_list_ready)
            self.bus.subscribe("background_light_changed",  self._on_background_light_changed)
            self.bus.subscribe("detection_led_changed",     self._on_detection_led_changed)
            self.bus.subscribe("frequency_config_changed",  self._on_frequency_config_changed)

        self.build_content()

    # ----------------------------------------------------------
    # UI BUILDING
    # ----------------------------------------------------------
    def build_content(self):
        with dpg.child_window(tag="acquisition_child_" + self.UUID,
                              width=self.width,
                              height=self.height,
                              pos=self.pos):

            dpg.add_text("Sequence not ready.\nPlease press 'Process sequence'.",
                         tag="sequence_state_" + self.UUID,
                         color=(255, 0, 0))

            dpg.add_text("", tag="sequence_counter_" + self.UUID)

            dpg.add_progress_bar(tag="progress_bar_" + self.UUID,
                                 width=-1, default_value=0.0)

            with dpg.group(horizontal=True):
                dpg.add_text("Time left:", color=(180, 180, 180))
                dpg.add_text("--:--", tag="time_total_" + self.UUID, color=(100, 220, 255))

            with dpg.group(horizontal=True):
                dpg.add_button(label="Start",
                               tag="start_" + self.UUID,
                               callback=self._start_acquisition,
                               width=150)
                dpg.add_button(label="Stop",
                               tag="stop_" + self.UUID,
                               width=150,
                               callback=self._stop_acquisition)

            dpg.configure_item("start_" + self.UUID, enabled=False)
            dpg.configure_item("stop_" + self.UUID, enabled=False)

    # ----------------------------------------------------------
    # Entry point: sequence list is ready
    # ----------------------------------------------------------
    def _on_sequence_list_ready(self, **_):
        """Called when sequence_input has processed and stored all sequences."""
        self.decoded_sequence_list = self.state.get_decoded_sequence_list()
        self._ensure_worker_running()
        self._check_hardware()

        if self.is_ready and self.decoded_sequence_list:
            dpg.configure_item("start_" + self.UUID, enabled=True)
            self._set_status(
                f"{len(self.decoded_sequence_list)} sequence(s) ready. Click Start.",
                color=(0, 255, 0))
        elif not self.decoded_sequence_list:
            self._set_status("No sequences found. Check inputs.", color=(255, 100, 0))
        else:
            self._set_status("Hardware not connected.", color=(255, 0, 0))

    # ----------------------------------------------------------
    # Hardware check
    # ----------------------------------------------------------
    def _check_hardware(self):
        adc = self.state.get_adc_instance()
        # esp32 = self.state.get_esp32_instance()
        adc_ok = adc is not None and (adc.is_connected() if hasattr(adc, "is_connected") else True)
        # esp32_ok = esp32 is not None and (esp32.is_connected() if hasattr(esp32, "is_connected") else True)
        self.is_ready = adc_ok

    def _ensure_worker_running(self):
        if self.state is None:
            return
        if self.worker_thread is None or not self.worker_thread.is_alive():
            esp32 = self.state.get_esp32_instance()
            acq_type = self.state.acquisition_type
            if acq_type == "Frequency":
                self.worker_thread = FrequencyAcquisitionWorker(esp32=esp32)
            else:
                self.worker_thread = SequenceAcquisitionWorker(esp32=esp32)
            self.worker_thread.start()

    # ----------------------------------------------------------
    # Start / Stop (user buttons)
    # ----------------------------------------------------------
    def _start_acquisition(self):
        if not self.decoded_sequence_list:
            print("no squences ready")
            return

        self._ensure_worker_running()
        dpg.configure_item("start_" + self.UUID, enabled=False)
        dpg.configure_item("stop_" + self.UUID, enabled=True)

        self.stop_requested = False
        self.sequence_index = 0
        self.total_time = self.state.get_total_time()
        self._experiment_start_time = time.time()
        self._reset_seq_run_state()

        self._run_current_sequence()
        self._start_polling()

    def _stop_acquisition(self):
        self.stop_requested = True

        if self.worker_thread:
            self.worker_thread.send_command({"action": "stop"})

        self.polling_enabled = False
        self.polling_thread_stop.set()

        dpg.configure_item("start_" + self.UUID, enabled=True)
        dpg.configure_item("stop_" + self.UUID, enabled=False)
        dpg.set_value("progress_bar_" + self.UUID, 0.0)
        self._clear_time_displays()
        self._set_status("Acquisition stopped.", color=(255, 0, 0))
        self._set_counter("")

        self.bus.publish("clear_live")

    # ----------------------------------------------------------
    # Per-sequence execution
    # ----------------------------------------------------------
    def _reset_seq_run_state(self):
        self._ignored_count = 0
        self._avg_buf = []
        self._current_params = {}

    def _run_current_sequence(self):
        seq = self.decoded_sequence_list[self.sequence_index]
        total = len(self.decoded_sequence_list)

        # Load per-sequence parameters (seq[2] = stable n, added by sequence_handler)
        n = seq[2] if (isinstance(seq, (tuple, list)) and len(seq) > 2) else (self.sequence_index + 1)
        params = self.state.get_parameter_list(n) if self.state else None
        if params is None:
            params = dict(self.state.parameter_config) if self.state else {}
        self._current_params = params

        n_ignore = params.get("nbr_sequences_ignored", 0)
        n_avg    = params.get("nbr_of_averages", 1)

        self._set_status(
            f"Running sequence {self.sequence_index + 1}/{total}...",
            color=(255, 200, 0))
        if n_ignore > 0 or n_avg > 1:
            self._set_counter(f"ignore={n_ignore}  avg={n_avg}")

        # seq[3] holds a per-slot frequency_config for frequency acquisition (dict only)
        config = dict(self.current_config)
        if isinstance(seq, (tuple, list)) and len(seq) > 3 and isinstance(seq[3], dict):
            config["frequency_config"] = seq[3]

        self._run_start_time = time.time()
        self.worker_thread.send_command({
            "action": "configure",
            "sequence": seq[0],
            "nbr_of_points": seq[1],
            "experiment_type": self.acquisition_type,
            "config": config,
            "tab_name": self.tab_name,
        })
        self.worker_thread.send_command({"action": "start"})

    # ----------------------------------------------------------
    # Polling thread
    # ----------------------------------------------------------
    def _start_polling(self):
        # Wait for any previous polling thread to fully exit before clearing the
        # stop-event.  If we clear it while the old thread is still alive it gets
        # "un-stopped", steals messages from the new thread, and calls _on_all_done
        # a second time — killing the new thread before it reads any live data.
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=0.3)

        self.polling_enabled = True
        self.polling_thread_stop.clear()
        self.polling_thread = threading.Thread(
            target=self._poll_worker_results,
            daemon=True)
        self.polling_thread.start()
        # Drain the main-thread queue every frame
        self._schedule_drain()

    def _schedule_drain(self):
        dpg.set_frame_callback(dpg.get_frame_count() + 1, self._drain_main_thread_queue)

    def _drain_main_thread_queue(self):
        """Called on the main thread each frame — dispatches deferred events/callables."""
        try:
            while True:
                item = self._main_thread_queue.get_nowait()
                if callable(item):
                    item()
                else:
                    event, kwargs = item
                    self.bus.publish(event, **kwargs)
        except queue.Empty:
            pass
        # Keep scheduling while polling is active OR items are still pending
        if self.polling_enabled or not self._main_thread_queue.empty():
            self._schedule_drain()

    def _poll_worker_results(self):
        while not self.polling_thread_stop.is_set():
            if not self.polling_enabled:
                break
            if not self.worker_thread or not self.worker_thread.is_alive():
                break

            try:
                msg = self.worker_thread.result_queue.get(timeout=0.1)

                if msg["type"] == "live":
                    self._handle_live(msg)
                elif msg["type"] == "progress":
                    progress = max(0.001, min(1.0, msg["progress"]))
                    dpg.set_value("progress_bar_" + self.UUID, progress)
                    self._update_time_displays()
                elif msg["type"] == "final":
                    self._handle_final(msg)

            except Exception:
                pass

        self.polling_enabled = False

    # ----------------------------------------------------------
    # Message handlers
    # ----------------------------------------------------------
    def _on_background_light_changed(self, amplitude: float = 0.0, **_):
        self.current_config["background_light_data"] = amplitude

    def _on_detection_led_changed(self, intensity: float = 100.0, **_):
        self.current_config["detection_led_intensity"] = intensity

    def _on_frequency_config_changed(self, frequency_config: dict = None, **_):
        self.current_config["frequency_config"] = frequency_config or {}

    def _handle_live(self, msg):
        # Defer to main thread — plot_data creates/modifies DPG items
        self._main_thread_queue.put(("live_data", {"y": msg["y"], "x": msg["x"]}))

    def _update_progress_bar(self, progress: float):
        dpg.set_value("progress_bar_" + self.UUID, max(0.0, min(1.0, progress)))

    def _handle_final(self, msg):
        """One run finished. Apply processing, then average/ignore/advance.
        Runs on the polling thread — never call DPG directly here.
        Use _main_thread_queue for anything that touches DPG items."""
        params     = self._current_params
        n_baseline = params.get("baseline_points",          0)
        n_ignore   = params.get("nbr_sequences_ignored",    0)
        n_avg      = params.get("nbr_of_averages",          1)
        t_wait_ms  = params.get("time_between_averages_ms", 0)

        # ── Baseline subtraction ──────────────────────────────────────────
        y = np.array(msg["final_results"], dtype=float)
        if n_baseline > 0 and len(y) >= n_baseline:
            y -= float(np.mean(y[:n_baseline]))
        y_list      = y.tolist()
        time_values = msg["time_values"]

        # clear_live calls delete_item — must run on main thread
        self._main_thread_queue.put(("clear_live", {}))

        # ── Ignore phase ──────────────────────────────────────────────────
        if self._ignored_count < n_ignore:
            self._ignored_count += 1
            left = n_ignore - self._ignored_count
            self._set_counter(f"Ignoring... ({left} left)")
            if not self.stop_requested:
                if t_wait_ms > 0:
                    time.sleep(t_wait_ms / 1000.0)
                self._run_current_sequence()
            return

        # ── Averaging phase ───────────────────────────────────────────────
        self._avg_buf.append(y_list)
        run_number = len(self._avg_buf)

        if run_number < n_avg:
            self._set_counter(f"Averaging: run {run_number}/{n_avg}")
            # Deferred to main thread (creates new DPG series)
            self._main_thread_queue.put(("intermediate_data", {
                "time_values":   time_values,
                "final_results": y_list,
                "run":           run_number,
            }))
            if not self.stop_requested:
                if t_wait_ms > 0:
                    time.sleep(t_wait_ms / 1000.0)
                self._run_current_sequence()
            return

        # ── All averages done: compute mean and publish ───────────────────
        mean_y = np.mean(self._avg_buf, axis=0).tolist()
        # Deferred to main thread (creates new DPG series + container items)
        self._main_thread_queue.put(("clear_intermediates", {}))
        seq_entry = self.decoded_sequence_list.get(self.sequence_index)
        str_sequence = (seq_entry[3]
                        if isinstance(seq_entry, (tuple, list)) and len(seq_entry) > 3
                        else "")
        self._main_thread_queue.put(("final_data", {
            "time_values":   time_values,
            "final_results": mean_y,
            "sequence":      msg.get("sequence"),
            "str_sequence":  str_sequence,
            "series_id":     self.sequence_index,
            "n_avg":         n_avg,
        }))

        # ── Advance to next sequence ──────────────────────────────────────
        self.sequence_index += 1
        self._reset_seq_run_state()
        t_wait_between_sequences_ms = params.get("time_before_next_seq_ms", 0)
        if not self.stop_requested and self.sequence_index < len(self.decoded_sequence_list):
            if t_wait_between_sequences_ms > 0:
                time.sleep(t_wait_between_sequences_ms / 1000.0)
            self._run_current_sequence()
        else:
            self._on_all_done()

    def _on_all_done(self):
        """Called from polling thread — defer all DPG work to main thread."""
        self.polling_enabled = False
        self.polling_thread_stop.set()

        total = len(self.decoded_sequence_list)
        done  = self.sequence_index

        def _finish():
            dpg.configure_item("start_" + self.UUID, enabled=True)
            dpg.configure_item("stop_"  + self.UUID, enabled=False)
            dpg.set_value("progress_bar_" + self.UUID, 1.0)
            self._clear_time_displays()
            self._set_status(f"Done: {done}/{total} sequence(s) completed.",
                             color=(0, 200, 0))
            self._set_counter("")
            if self.bus:
                self.bus.publish("acquisition_complete")

        self._main_thread_queue.put(_finish)

    # ----------------------------------------------------------
    # UI helpers
    # ----------------------------------------------------------
    def _set_status(self, text, color=(255, 255, 255)):
        dpg.set_value("sequence_state_" + self.UUID, text)
        dpg.configure_item("sequence_state_" + self.UUID, color=color)

    def _set_counter(self, text):
        dpg.set_value("sequence_counter_" + self.UUID, text)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = max(0.0, seconds)
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m}:{s:02d}"

    def _update_time_displays(self):
        """Display total experiment time remaining (total_time - elapsed)."""
        if self._experiment_start_time is None or self.total_time is None:
            return
        elapsed = time.time() - self._experiment_start_time
        remaining = self.total_time / 1000.0 - elapsed
        dpg.set_value("time_total_" + self.UUID, self._fmt_time(remaining))

    def _clear_time_displays(self):
        dpg.set_value("time_total_" + self.UUID, "--:--")

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------
    def shutdown(self):
        self.polling_enabled = False
        self.polling_thread_stop.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.send_command({"action": "shutdown"})
            self.worker_thread.join(timeout=2.0)
            if self.worker_thread.is_alive():
                self.worker_thread.shutdown_forcefully()
                self.worker_thread.join(timeout=1.0)

    def cleanup(self):
        self.shutdown()

    def _on_window_close(self):
        self.cleanup()
