from __future__ import annotations

import ctypes
import logging
import threading
import time
import queue
from typing import Optional, List

import numpy as np

from mcculw import ul
from mcculw.enums import (
    ULRange,
    FunctionType,
    ScanOptions,
    InfoType,
    BoardInfo,
)
from mcculw.device_info import DaqDeviceInfo

from config.config import config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ADCError(RuntimeError):
    pass


class ADCBase:
    """Base ADC helper with common functionality.

    Responsibilities:
    - board/device info
    - safe buffer allocation/free
    - conversion helpers
    - reader thread that pushes full trigger blocks onto a queue
    - shared AI scan setup
    """

    def __init__(self, board_num: int | None = None):
        self.board_num = config["ADC"].get("board_num")

        # Initialize dev_info eagerly so subclasses can use it without
        # having to call is_connected() first.
        try:
            self.dev_info = DaqDeviceInfo(self.board_num)
        except Exception:
            self.dev_info = None

        self.samples_per_trigger = config["Sampling"]["samples_per_trigger"]
        self.channel_count = config["ADC"]["channel_count"]
        self.nbr_of_triggers_per_sample = config["Sampling"]["nbr_of_triggers_per_sample"]
        self.adc_bit_depth = config["ADC"]["adc_bit_depth"]
        self.actinic_light_max = config["LED"]["actinic_light_max"]
        self.actinic_light_offset = config["LED"]["actinic_light_offset"]
        self.detection_light_max = config["LED"]["detection_light_max"]
        self.detection_light_offset = config["LED"]["detection_light_offset"]

        self._memhandle_output: Optional[int] = None
        self._memhandle_input: Optional[int] = None
        self._c_data_array = None
        self._c_waveform_array = None

        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._data_queue: queue.Queue = queue.Queue()

    # ---------------------------
    # Device utilities
    # ---------------------------
    def is_connected(self) -> bool:
        try:
            devices = ul.get_daq_device_inventory(7, number_of_devices=1)
            self.dev_info = DaqDeviceInfo(self.board_num)
            return bool(devices)
        except Exception as e:
            logger.exception("Error checking device inventory: %s", e)
            return False

    # ---------------------------
    # Buffer management
    # ---------------------------
    def _alloc_acq_buffer_32(self, num_values: int) -> None:
        self._free_acq_buffer()
        self._memhandle_acq = ul.win_buf_alloc_32(num_values)
        if not self._memhandle_acq:
            raise ADCError("Failed to allocate acquisition buffer")
        self._acq_buffer_size = num_values
        self._c_data_array = ctypes.cast(self._memhandle_acq, ctypes.POINTER(ctypes.c_ulong))
        logger.debug("Allocated acq buffer (32-bit) size=%d", num_values)

    def _alloc_waveform_buffer_16(self, num_values: int) -> None:
        self._free_waveform_buffer()
        self._memhandle = ul.win_buf_alloc(num_values)
        if not self._memhandle:
            raise ADCError("Failed to allocate waveform buffer")
        self._c_waveform_array = ctypes.cast(self._memhandle, ctypes.POINTER(ctypes.c_ushort))
        logger.debug("Allocated waveform buffer (16-bit) size=%d", num_values)

    def _free_acq_buffer(self) -> None:
        if getattr(self, "_memhandle_acq", None):
            try:
                ul.win_buf_free(self._memhandle_acq)
            except Exception:
                logger.exception("Failed freeing acquisition buffer")
            finally:
                self._memhandle_acq = None
                self._c_data_array = None

    def _free_waveform_buffer(self) -> None:
        if getattr(self, "_memhandle", None):
            try:
                ul.win_buf_free(self._memhandle)
            except Exception:
                logger.exception("Failed freeing waveform buffer")
            finally:
                self._memhandle = None
                self._c_waveform_array = None

    def shutdown(self) -> None:
        """Stop reader and free buffers — safe to call multiple times."""
        self.stop_reader()
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.AIFUNCTION)
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        except Exception as e:
            if "not running" not in str(e).lower():
                logger.exception("Error stopping background acquisition")
        self._free_acq_buffer()
        self._free_waveform_buffer()

    # ---------------------------
    # Shared AI scan setup
    # ---------------------------
    def _configure_trigger_count(self) -> None:
        """Write samples_per_trigger to the board's trigger-count register."""
        ul.set_config(
            info_type=InfoType.BOARDINFO,
            board_num=self.board_num,
            dev_num=0,
            config_item=BoardInfo.ADTRIGCOUNT,
            config_val=self.samples_per_trigger,
        )

    def _start_ai_scan(self, total_points: int) -> None:
        """Start a retriggered background AI scan into the pre-allocated acq buffer."""
        ul.a_in_scan(
            board_num=self.board_num,
            low_chan=0,
            high_chan=self.channel_count - 1,
            num_points=total_points,
            rate=1,  # ignored — acquisition is clocked externally
            ul_range=ULRange.BIP10VOLTS,
            memhandle=self._memhandle_acq,
            options=(ScanOptions.EXTTRIGGER
                     |ScanOptions.BACKGROUND
                | ScanOptions.CONTINUOUS
                | ScanOptions.RETRIGMODE
            ),
        )

    # ---------------------------
    # Conversion helpers
    # ---------------------------
    def to_voltage_32(self, raw: int, ul_range: ULRange = ULRange.BIP10VOLTS) -> float:
        return ul.to_eng_units_32(board_num=self.board_num, ul_range=ul_range, data_value=raw)

    def from_voltage_16(self, volts: float, ao_range) -> int:
        return int(ul.from_eng_units(self.board_num, ao_range, volts))

    # ---------------------------
    # Reader thread
    # ---------------------------
    def start_reader(self) -> None:
        if self._reader_thread is None or not self._reader_thread.is_alive():
            self._stop_event.clear()
            while not self._data_queue.empty():
                try:
                    self._data_queue.get_nowait()
                except queue.Empty:
                    break
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()
            logger.debug("Started ADC reader thread")

    def stop_reader(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=timeout)
            if self._reader_thread.is_alive():
                logger.warning("Reader thread did not stop cleanly")

    def _reader_loop(self) -> None:
        """Poll the acquisition buffer and push completed trigger blocks to the queue."""
        last_count = 0
        trigger_block: List[int] = []

        while not self._stop_event.is_set():
            try:
                with self._lock:
                    cur_count = self.get_status()

                # Clamp to buffer size: in CONTINUOUS mode cur_count grows past the
                # allocated buffer, which would cause an out-of-bounds memory access.
                buf_size = getattr(self, "_acq_buffer_size", None)
                if buf_size is not None:
                    cur_count = min(cur_count, buf_size)

                if cur_count > last_count:
                    if self._c_data_array is not None:
                        for i in range(last_count, cur_count):
                            trigger_block.append(self._c_data_array[i])
                    last_count = cur_count

                    block_size = self.samples_per_trigger * self.nbr_of_triggers_per_sample
                    while len(trigger_block) >= block_size:
                        block_to_push = trigger_block[:block_size]
                        self._data_queue.put(block_to_push)
                        trigger_block = trigger_block[block_size:]

                time.sleep(0.001)

            except Exception as e:
                logger.exception("Error in reader loop: %s", e)
                break

    def read_block(self, timeout: Optional[float] = None) -> Optional[List[int]]:
        try:
            return self._data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ---------------------------
    # Low-level status
    # ---------------------------
    def get_status(self) -> int:
        _, cur_count, _ = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
        return cur_count

    def set_detection_led(self, amplitude: float) -> None:
        """Set detection LED intensity (0–100) on AO channel 1."""
        count_max = self.adc_bit_depth
        val = int(count_max * (0.5 + 0.5 * amplitude / self.detection_light_max) - self.detection_light_offset)
        ul.a_out(
            board_num=self.board_num,
            channel=1,
            ul_range=ULRange.BIP10VOLTS,
            data_value=max(0, min(count_max, val)),
        )

    def stop_acquisition(self) -> None:
        raise NotImplementedError

    def set_background_light(self, amplitude: float) -> None:
        count_max = self.adc_bit_depth
        amplitude = int(count_max * (0.5 + 0.5 * amplitude / self.actinic_light_max) - self.actinic_light_offset)
        ul.a_out(
            board_num=self.board_num,
            channel=0,
            ul_range=ULRange.BIP10VOLTS,
            data_value=int(amplitude),
        )
