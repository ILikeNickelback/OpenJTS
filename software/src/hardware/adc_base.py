"""Base ADC driver for MCC DAQ boards.

Provides shared infrastructure used by all concrete ADC subclasses:
buffer allocation/deallocation, a background reader thread that delivers
completed trigger blocks via a queue, AI scan configuration, unit-conversion
helpers, and LED output control.
"""

import ctypes
import threading
import time
import queue
import numpy as np

from loguru import logger
from mcculw import ul
from mcculw.enums import (
    ULRange,
    FunctionType,
    ScanOptions,
    InfoType,
    BoardInfo,
    ChannelType,
)

from mcculw.device_info import DaqDeviceInfo

from config.config import config


class ADCError(RuntimeError):
    """Raised when an MCC DAQ operation fails."""


class ADCBase():
    """Base ADC helper for MCC DAQ boards.

    Manages the board connection, DMA buffer lifecycle, a background reader
    thread, AI scan setup, and analog output for LED control.  Subclasses
    must implement :meth:`stop_acquisition` for their specific scan type.

    Attributes:
        board_num (int): MCC board number from ``config.json``.
        dev_info (DaqDeviceInfo | None): Board capability info; ``None`` if
            the board is not detected at startup.
        samples_per_trigger (int): ADC samples captured per external trigger.
        channel_count (int): Number of AI channels scanned per trigger.
        nbr_of_triggers_per_sample (int): Triggers accumulated into one data block.
        adc_bit_depth (int): Full-scale raw count (e.g. 65535 for 16-bit).
        actinic_light_max (int): Maximum actinic LED intensity value (config units).
        actinic_light_offset (int): DAC offset for the actinic LED channel.
        detection_light_max (int): Maximum detection LED intensity value (config units).
        detection_light_offset (int): DAC offset for the detection LED channel.
    """

    def __init__(self):
        """Load hardware parameters from config and initialise all internal state."""
        self.board_num = config["ADC"].get("board_num")

        # Initialise dev_info eagerly so subclasses can query capabilities
        # without having to call is_connected() first.
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

        # DMA buffer handles and ctypes array pointers
        self._memhandle_acq: int | None = None    # 32-bit acquisition buffer
        self._memhandle: int | None = None         # 16-bit waveform output buffer
        self._acq_buffer_size: int | None = None   # number of values in acq buffer
        self._c_data_array = None                  # ctypes view of _memhandle_acq
        self._c_waveform_array = None              # ctypes view of _memhandle

        # Reader thread primitives
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._data_queue: queue.Queue = queue.Queue()

    # ------------------------------------------------------------------
    # Device utilities
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """Return ``True`` if at least one MCC DAQ device is detected.

        Also refreshes :attr:`dev_info` as a side effect.
        """
        try:
            devices = ul.get_daq_device_inventory(7, number_of_devices=1)
            self.dev_info = DaqDeviceInfo(self.board_num)
            return bool(devices)
        except Exception as e:
            logger.exception("Error checking device inventory: %s", e)
            return False

    # ------------------------------------------------------------------
    # Buffer management
    # ------------------------------------------------------------------

    def _alloc_acq_buffer_32(self, num_values: int) -> None:
        """Allocate a 32-bit DMA acquisition buffer of *num_values* samples.

        Any previously allocated acquisition buffer is freed first.

        Args:
            num_values: Total number of 32-bit samples the buffer must hold.

        Raises:
            ADCError: If the MCC library fails to allocate the buffer.
        """
        self._free_acq_buffer()
        self._memhandle_acq = ul.win_buf_alloc_32(num_values)
        if not self._memhandle_acq:
            raise ADCError("Failed to allocate acquisition buffer")
        self._acq_buffer_size = num_values
        self._c_data_array = ctypes.cast(self._memhandle_acq, ctypes.POINTER(ctypes.c_ulong))
        logger.debug("Allocated acq buffer (32-bit) size=%d", num_values)

    def _alloc_waveform_buffer_16(self, num_values: int) -> None:
        """Allocate a 16-bit DMA waveform output buffer of *num_values* samples.

        Any previously allocated waveform buffer is freed first.

        Args:
            num_values: Total number of 16-bit samples the buffer must hold.

        Raises:
            ADCError: If the MCC library fails to allocate the buffer.
        """
        self._free_waveform_buffer()
        self._memhandle = ul.win_buf_alloc(num_values)
        if not self._memhandle:
            raise ADCError("Failed to allocate waveform buffer")
        self._c_waveform_array = ctypes.cast(self._memhandle, ctypes.POINTER(ctypes.c_ushort))
        logger.debug("Allocated waveform buffer (16-bit) size=%d", num_values)

    def _free_acq_buffer(self) -> None:
        """Release the 32-bit acquisition DMA buffer if allocated."""
        if self._memhandle_acq is not None:
            try:
                ul.win_buf_free(self._memhandle_acq)
            except Exception:
                logger.exception("Failed freeing acquisition buffer")
            finally:
                self._memhandle_acq = None
                self._c_data_array = None

    def _free_waveform_buffer(self) -> None:
        """Release the 16-bit waveform DMA buffer if allocated."""
        if self._memhandle is not None:
            try:
                ul.win_buf_free(self._memhandle)
            except Exception:
                logger.exception("Failed freeing waveform buffer")
            finally:
                self._memhandle = None
                self._c_waveform_array = None

    def shutdown(self) -> None:
        """Stop the reader thread, halt background scans, and free all buffers.

        Safe to call multiple times or when no acquisition is running.
        """
        self.stop_reader()
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.AIFUNCTION)
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        except Exception as e:
            if "not running" not in str(e).lower():
                logger.exception("Error stopping background acquisition")
        self._free_acq_buffer()
        self._free_waveform_buffer()

    # ------------------------------------------------------------------
    # Shared AI scan setup
    # ------------------------------------------------------------------

    def _configure_trigger_count(self) -> None:
        """Write :attr:`samples_per_trigger` to the board's trigger-count register."""
        ul.set_config(
            info_type=InfoType.BOARDINFO,
            board_num=self.board_num,
            dev_num=0,
            config_item=BoardInfo.ADTRIGCOUNT,
            config_val=self.samples_per_trigger,
        )

    def _start_ai_scan(self, total_points: int) -> None:
        """Start a retriggered background AI scan into the pre-allocated acq buffer.

        The scan is clocked externally (``rate=1`` is ignored by the board).
        Uses ``EXTTRIGGER | BACKGROUND | CONTINUOUS | RETRIGMODE`` so the board
        re-arms automatically after each trigger.

        Args:
            total_points: Total number of samples across all channels to
                allocate in the scan (must match the allocated buffer size).
        """
        ul.a_in_scan(
            board_num=self.board_num,
            low_chan=0,
            high_chan=self.channel_count - 1,
            num_points=total_points,
            rate=1,
            ul_range=ULRange.BIP10VOLTS,
            memhandle=self._memhandle_acq,
            options=(
                ScanOptions.EXTTRIGGER
                | ScanOptions.BACKGROUND
                | ScanOptions.CONTINUOUS
                | ScanOptions.RETRIGMODE
            ),
        )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_voltage_32(self, raw: int, ul_range: ULRange = ULRange.BIP10VOLTS) -> float:
        """Convert a raw 32-bit ADC count to engineering units (volts).

        Args:
            raw: Raw 32-bit count read from the acquisition buffer.
            ul_range: Voltage range used during the scan.

        Returns:
            Voltage in volts.
        """
        return ul.to_eng_units_32(board_num=self.board_num, ul_range=ul_range, data_value=raw)

    def from_voltage_16(self, volts: float, ao_range) -> int:
        """Convert a voltage to a 16-bit DAC count for analog output.

        Args:
            volts: Desired output voltage.
            ao_range: AO voltage range constant (MCC ``ULRange``).

        Returns:
            16-bit integer DAC count.
        """
        return int(ul.from_eng_units(self.board_num, ao_range, volts))

    # ------------------------------------------------------------------
    # Reader thread
    # ------------------------------------------------------------------

    def start_reader(self) -> None:
        """Start the background reader thread if it is not already running.

        Clears the data queue and stop event before launching the thread so
        stale data from a previous acquisition is discarded.
        """
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
        """Signal the reader thread to stop and wait for it to exit.

        Args:
            timeout: Maximum seconds to wait for the thread to join.
        """
        self._stop_event.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=timeout)
            if self._reader_thread.is_alive():
                logger.warning("Reader thread did not stop cleanly")

    def _reader_loop(self) -> None:
        """Poll the acquisition buffer and push completed trigger blocks to the queue.

        Runs on the reader thread. Accumulates raw samples from the DMA buffer
        into ``trigger_block`` and enqueues a slice every time a full block
        (``samples_per_trigger x nbr_of_triggers_per_sample``) is available.

        The sample count is clamped to :attr:`_acq_buffer_size` to prevent
        out-of-bounds memory access in ``CONTINUOUS`` scan mode, where the
        MCC status counter grows beyond the allocated buffer size.
        """
        last_count = 0
        trigger_block: list[int] = []

        while not self._stop_event.is_set():
            try:
                with self._lock:
                    cur_count = self.get_status()

                if self._acq_buffer_size is not None:
                    cur_count = min(cur_count, self._acq_buffer_size)

                if cur_count > last_count:
                    if self._c_data_array is not None:
                        for i in range(last_count, cur_count):
                            trigger_block.append(self._c_data_array[i])
                    last_count = cur_count

                    block_size = self.samples_per_trigger * self.nbr_of_triggers_per_sample
                    while len(trigger_block) >= block_size:
                        self._data_queue.put(trigger_block[:block_size])
                        trigger_block = trigger_block[block_size:]

                time.sleep(0.001)

            except Exception as e:
                logger.exception("Error in reader loop: %s", e)
                break

    def read_block(self, timeout: float | None = None) -> list[int] | None:
        """Retrieve the next completed trigger block from the queue.

        Args:
            timeout: Seconds to wait for a block; ``None`` waits indefinitely.

        Returns:
            A list of raw integer samples, or ``None`` if the queue is empty
            and the timeout expires.
        """
        try:
            return self._data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Low-level status and output
    # ------------------------------------------------------------------

    def get_status(self) -> int:
        """Return the current AI scan sample count from the MCC driver.

        Returns:
            Number of samples transferred to the acquisition buffer so far.
        """
        _, cur_count, _ = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
        return cur_count

    def set_detection_led(self, amplitude: float) -> None:
        """Set the detection LED intensity on AO channel 1.

        Args:
            amplitude: Desired intensity in config units (0 to detection_light_max).
        """
        count_max = self.adc_bit_depth
        val = int(count_max * (0.5 + 0.5 * amplitude / self.detection_light_max) - self.detection_light_offset)
        ul.a_out(
            board_num=self.board_num,
            channel=1,
            ul_range=ULRange.BIP10VOLTS,
            data_value=max(0, min(count_max, val)),
        )

    def set_background_light(self, amplitude: float) -> None:
        """Set the actinic (background) light intensity on AO channel 0.

        Args:
            amplitude: Desired intensity in config units (0 to actinic_light_max).
        """
        count_max = self.adc_bit_depth
        val = int(count_max * (0.5 + 0.5 * amplitude / self.actinic_light_max) - self.actinic_light_offset)
        ul.a_out(
            board_num=self.board_num,
            channel=0,
            ul_range=ULRange.BIP10VOLTS,
            data_value=val,
        )
    
    
    def start_acquisition(self) -> None:
        """Start the retriggered AI scan then the AO/digital output scan.

        The AI scan is started first so the board is already listening for
        triggers when the stimulus waveform begins.
        """
        self._start_ai_scan(self._total_acq_samples)

        ao_range = self.dev_info.get_ao_info().supported_ranges[0]
        ul.daq_out_scan(
            self.board_num,
            [0, 1, 1],
            [ChannelType.ANALOG, ChannelType.ANALOG, ChannelType.DIGITAL],
            [ao_range, ao_range, ULRange.NOTUSED],
            3,
            self.rate,
            self._total_waveform_samples * 3,
            self._memhandle,
            options=(ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS),
        )

    def stop_acquisition(self) -> None:
        """Stop both background scans and free all DMA buffers.

        Buffer cleanup runs unconditionally via ``finally`` so memory is never
        leaked even if a stop call raises.
        """
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.AIFUNCTION)
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        finally:
            self._free_acq_buffer()
            self._free_waveform_buffer()

    def reset_actinic_light(self) -> None:
        """Zero both AO channels after acquisition ends.

        Outputs a single two-channel sample at 0 V on AO 0 and AO 1 so the
        actinic LED is not left at its last waveform value.
        """
        self._alloc_waveform_buffer_16(2)
        if self._c_waveform_array is not None:
            arr_view = np.ctypeslib.as_array(self._c_waveform_array, shape=(2,))
            arr_view[:] = [0, 0]

        ao_range = self.dev_info.get_ao_info().supported_ranges[0]
        ul.a_out_scan(
            board_num=self.board_num,
            low_chan=0,
            high_chan=1,
            num_points=1,
            rate=1,
            ul_range=ao_range,
            memhandle=self._memhandle,
            options=None,
        )