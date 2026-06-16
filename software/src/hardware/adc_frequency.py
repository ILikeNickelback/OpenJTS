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
from sequence_builders.frequency_waveform_builder import FrequencyWaveformBuilder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class FrequencyAcquisitionADC(ADCBase):
    """ADC acquisition for frequency-based experiments.

    The ADC board generates the stimulus waveform (sinusoidal actinic + detection
    pulses) and simultaneously captures the AI data.

    Lifecycle
    ---------
        configure(frequency_config) -> int   build waveform, allocate buffers
        start_reader()                       start background reader thread (base)
        start_acquisition()                  start AI scan + AO/digital output scan
        -- acquisition runs --
        stop_acquisition()                   stop all scans, free buffers
        reset_actinic_light()                zero AO outputs after acquisition
    """

    def __init__(self, board_num: int | None = None):
        super().__init__(board_num=board_num)
        self.rate: float = config["ADC"]["sampling_rate"]
        self._total_waveform_samples: int = 0
        self._total_acq_samples: int = 0
        self._waveform_builder = FrequencyWaveformBuilder(self.board_num, self.rate)
        self.pulse_times_ms: list[float] = []

    def configure(self, frequency_config: dict) -> int:
        """Prepare buffers, waveform data, and board registers.

        Returns the number of logical acquisition points so the worker can set
        nbr_of_points without having to know waveform internals.
        """
        for port in self.dev_info.get_dio_info().port_info:
            if port.is_port_configurable:
                ul.d_config_port(self.board_num, port.type, DigitalIODirection.OUT)

        # self._waveform_builder.plot(frequency_config)
        interleaved, self._total_waveform_samples, number_of_pulses = (self._waveform_builder.build(frequency_config))
        self.pulse_times_ms = self._waveform_builder.pulse_times_ms

        self.nbr_of_triggers_per_sample = 1 + config["Sampling"].get("number_of_points_before_flash", 1)
        self._total_acq_samples = number_of_pulses * self.samples_per_trigger * self.nbr_of_triggers_per_sample

        self._alloc_waveform_buffer_16(len(interleaved))
        if self._c_waveform_array is not None:
            arr_view = np.ctypeslib.as_array(self._c_waveform_array, shape=(len(interleaved),))
            arr_view[:] = interleaved

        self._alloc_acq_buffer_32(self._total_acq_samples)
        self._configure_trigger_count()

        return number_of_pulses

    def start_acquisition(self) -> None:
        """Start AI scan (retriggered background) then AO/digital output scan."""
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
            options=(
                ScanOptions.BACKGROUND
                | ScanOptions.CONTINUOUS
            )
        )

    def stop_acquisition(self) -> None:
        try:
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.AIFUNCTION)
            ul.stop_background(board_num=self.board_num, function_type=FunctionType.DAQOFUNCTION)
        finally:
            self._free_acq_buffer()
            self._free_waveform_buffer()

    def reset_actinic_light(self) -> None:
        """Zero both AO channels by outputting a two-sample flat waveform."""
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
