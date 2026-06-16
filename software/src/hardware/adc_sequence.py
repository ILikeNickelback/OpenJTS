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
from sequence_builders.sequence_waveform_builder import SequenceWaveformBuilder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SequenceAcquisitionADC(ADCBase):
    """ADC acquisition for sequence-based experiments.

    The ADC board generates the stimulus waveform (decoded sequence tokens →
    actinic + detection pulses) and simultaneously captures the AI data.

    Lifecycle
    ---------
        configure(sequence) -> int   build waveform from tokens, allocate buffers
        start_reader()               start background reader thread (base)
        start_acquisition()          start AI scan + AO/digital output scan
        -- acquisition runs --
        stop_acquisition()           stop all scans, free buffers
        reset_actinic_light()        zero AO outputs after acquisition
    """

    def __init__(self, board_num: int | None = None):
        super().__init__(board_num=board_num)
        self.rate: float = config["ADC"]["sampling_rate"]
        self._total_waveform_samples: int = 0
        self._total_acq_samples: int = 0
        self._waveform_builder = SequenceWaveformBuilder(self.board_num, self.rate)

    def configure(self, sequence) -> int:
        """Build the waveform, allocate buffers and arm board registers.

        Parameters
        ----------
        sequence : decoded token list produced by sequence_control.decode_sequence()

        Returns
        -------
        int : number of logical acquisition points (pulses), so the worker can
              set nbr_of_points without knowing waveform internals.
        """
        for port in self.dev_info.get_dio_info().port_info:
            if port.is_port_configurable:
                ul.d_config_port(self.board_num, port.type, DigitalIODirection.OUT)

        interleaved, self._total_waveform_samples, number_of_pulses = (
            self._waveform_builder.build(sequence)
        )
        self._total_acq_samples = (
            number_of_pulses
            * self.samples_per_trigger
            * config["Sampling"]["nbr_of_triggers_per_sample"]
        )

        self._alloc_waveform_buffer_16(len(interleaved))
        if self._c_waveform_array is not None:
            arr_view = np.ctypeslib.as_array(
                self._c_waveform_array, shape=(len(interleaved),)
            )
            arr_view[:] = interleaved

        self._alloc_acq_buffer_32(self._total_acq_samples)
        self._configure_trigger_count()

        logger.info(
            "Configured sequence acquisition: pulses=%d  total_acq_samples=%d",
            number_of_pulses,
            self._total_acq_samples,
        )
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
            options=(ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS),
        )

    def stop_acquisition(self) -> None:
        try:
            ul.stop_background(board_num=self.board_num,
                               function_type=FunctionType.AIFUNCTION)
            ul.stop_background(board_num=self.board_num,
                               function_type=FunctionType.DAQOFUNCTION)
        finally:
            self._free_acq_buffer()
            self._free_waveform_buffer()

    def reset_actinic_light(self) -> None:
        """Zero both AO channels after acquisition."""
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
