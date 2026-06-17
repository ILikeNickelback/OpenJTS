"""ADC driver subclass for detection LED calibration.

Provides a continuous-retriggered AI scan with a large rolling buffer so the
calibration worker can read pairs of photodiode triggers indefinitely.  The
companion AO/digital output scan drives the detection LED at a fixed low
frequency (1 Hz) set by ``config["Calibration"]``.
"""

import numpy as np
from mcculw import ul
from mcculw.enums import (
    ULRange,
    FunctionType,
    ScanOptions,
    ChannelType,
    DigitalIODirection,
)

from config.config import config

from sequence_builders.calibration_waveform_builder import CalibrationWaveformBuilder
from hardware.adc_base import ADCBase


class CalibrationAcquisitionADC(ADCBase):
    """ADC driver for detection LED calibration.

    Keeps a large rolling acquisition buffer (``samples_per_trigger *
    BUFFER_SIZE_MULTIPLIER`` points) so the calibration worker can consume
    trigger pairs continuously without knowing the total sample count in
    advance.

    Typical call order::

        adc = CalibrationAcquisitionADC()
        adc.configure()                          # allocate buffer, arm AI scan
        adc.start_calibration_using_adc(100.0)  # start LED waveform output
        adc.start_reader()                       # begin background read loop
        # ... consume blocks via adc.read_block() ...
        adc.stop_acquisition()                   # stop AI scan, free AI buffer
        adc.stop_calibration_using_adc()         # stop AO/digital output

    Attributes:
        BUFFER_SIZE_MULTIPLIER (int): Scales the acquisition buffer relative to
            ``samples_per_trigger``.  A larger value reduces the risk of
            overrun at the cost of more memory.
    """

    BUFFER_SIZE_MULTIPLIER = 1000

    def configure(self) -> None:
        """Allocate the acquisition buffer and arm the retriggered AI scan.

        Buffer size is ``samples_per_trigger * BUFFER_SIZE_MULTIPLIER``.
        """
        total_buffer_points = self.samples_per_trigger * self.BUFFER_SIZE_MULTIPLIER
        self._alloc_acq_buffer_32(total_buffer_points)
        self._configure_trigger_count()
        self._start_ai_scan(total_buffer_points)

    def start_calibration_using_adc(self, intensity: float = 100.0) -> None:
        """Build and start the detection LED waveform on the AO/digital outputs.

        Configures all configurable digital ports as outputs, builds an
        interleaved waveform via :class:`CalibrationWaveformBuilder`, copies it
        into a 16-bit DMA buffer, and starts a continuous ``daq_out_scan``
        driving AO channels 0 and 1 plus one digital channel.

        Args:
            intensity: Detection LED intensity as a percentage (0–100).
        """
        calibration_config = config["Calibration"]

        for port in self.dev_info.get_dio_info().port_info:
            if port.is_port_configurable:
                ul.d_config_port(self.board_num, port.type, DigitalIODirection.OUT)

        rate = config["ADC"]["sampling_rate"]
        builder = CalibrationWaveformBuilder(self.board_num, rate)
        interleaved, total_waveform_samples, _ = builder.build(calibration_config, intensity=intensity)

        self._alloc_waveform_buffer_16(len(interleaved))
        if self._c_waveform_array is not None:
            arr_view = np.ctypeslib.as_array(self._c_waveform_array, shape=(len(interleaved),))
            arr_view[:] = interleaved

        ao_range = self.dev_info.get_ao_info().supported_ranges[0]
        ul.daq_out_scan(
            self.board_num,
            [0, 1, 1],
            [ChannelType.ANALOG, ChannelType.ANALOG, ChannelType.DIGITAL],
            [ao_range, ao_range, ULRange.NOTUSED],
            3,
            rate,
            total_waveform_samples * 3,
            self._memhandle,
            options=(ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS),
        )

    def stop_calibration_using_adc(self) -> None:
        """Stop the AO/digital output scan."""
        ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)


    def update_detection_intensity(self, intensity: float) -> None:
        """Restart the AO output scan at a new detection LED intensity.

        Stops the running scan (ignoring errors if it has already stopped),
        then rebuilds and restarts the waveform at the new intensity.

        Args:
            intensity: New detection LED intensity as a percentage (0–100).
        """
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        except Exception:
            pass
        self.start_calibration_using_adc(intensity=intensity)

    def stop_acquisition(self) -> None:
        """Stop both background scans and free the acquisition buffer.

        The AI and AO/digital scans are both stopped before the buffer is
        released.  Buffer cleanup runs unconditionally via ``finally`` so
        memory is never leaked even if a stop call raises.
        """
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.AIFUNCTION)
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        finally:
            self._free_acq_buffer()
            self._free_waveform_buffer()