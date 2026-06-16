from __future__ import annotations

import logging

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
from hardware.adc_base import ADCBase
from sequence_builders.calibration_waveform_builder import CalibrationWaveformBuilder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CalibrationAcquisitionADC(ADCBase):
    """Acquisition mode for calibration.

    Keeps a large rolling buffer so the worker can read pairs of triggers
    continuously without knowing in advance how many points will be collected.

    API:
        configure()                      -- allocate buffer + arm AI scan
        start_calibration_using_adc()    -- start AO output (frequency mode only)
        stop_calibration_using_adc()     -- stop AO output
        stop_acquisition()               -- stop AI scan + free AI buffer
    """

    BUFFER_SIZE_MULTIPLIER = 1000

    def configure(self) -> None:
        """Allocate the acquisition buffer and arm the AI scan."""
        total_buffer_points = self.samples_per_trigger * self.BUFFER_SIZE_MULTIPLIER
        self._alloc_acq_buffer_32(total_buffer_points)
        self._configure_trigger_count()
        self._start_ai_scan(total_buffer_points)

    def start_calibration_using_adc(self, intensity: float = 100.0) -> None:
        """Build and start a low-frequency calibration waveform on the AO/digital outputs."""
        calibration_config = config["Calibration"]

        for port in self.dev_info.get_dio_info().port_info:
            if port.is_port_configurable:
                ul.d_config_port(self.board_num, port.type, DigitalIODirection.OUT)

        rate = config["ADC"]["sampling_rate"]
        builder = CalibrationWaveformBuilder(self.board_num, rate)
        # builder.plot(calibration_config)
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
            options=(ScanOptions.BACKGROUND| ScanOptions.CONTINUOUS),
        )

    def stop_calibration_using_adc(self) -> None:
        """Stop the AO/digital output scan started by start_calibration_using_adc."""
        ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)

    def update_detection_intensity(self, intensity: float) -> None:
        """Stop the running AO scan, rebuild the waveform at the new intensity, and restart."""
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        except Exception:
            pass
        self.start_calibration_using_adc(intensity=intensity)

    def stop_acquisition(self) -> None:
        """Stop the AI scan and free the acquisition buffer."""
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.AIFUNCTION)
        finally:
            self._free_acq_buffer()


   