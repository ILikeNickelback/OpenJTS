"""ADC driver subclass for sequence-based experiments.

The board simultaneously generates a stimulus waveform (decoded sequence tokens
converted to actinic + detection pulses by :class:`SequenceWaveformBuilder`) on
its AO/digital outputs and captures the photodiode response on its AI inputs
using a retriggered background scan.
"""

import numpy as np
from loguru import logger
from mcculw import ul
from mcculw.enums import (
    DigitalIODirection,
)

from config.config import config
from sequence_builders.sequence_waveform_builder import SequenceWaveformBuilder
from hardware.adc_base import ADCBase


class SequenceAcquisitionADC(ADCBase):
    """ADC driver for sequence-based experiments.

    Generates a multi-channel stimulus waveform from a decoded sequence token
    list on the board's AO/digital outputs while simultaneously capturing the
    photodiode response on the AI inputs via a retriggered background scan.

    Typical call order::

        adc = SequenceAcquisitionADC()
        n_pulses = adc.configure(decoded_sequence)  # build waveform, allocate buffers
        adc.start_reader()                           # start background reader thread
        adc.start_acquisition()                      # start AI + AO/digital scans
        # ... consume blocks via adc.read_block() ...
        adc.stop_acquisition()                       # stop all scans, free buffers
        adc.reset_actinic_light()                    # zero AO outputs

    Attributes:
        rate (float): ADC/DAC sampling rate in Hz, from ``config["ADC"]["sampling_rate"]``.
    """

    def __init__(self):
        """Initialise the waveform builder and internal sample counters."""
        super().__init__()
        self.rate: float = config["ADC"]["sampling_rate"]
        self._total_waveform_samples: int = 0
        self._total_acq_samples: int = 0
        self._waveform_builder = SequenceWaveformBuilder(self.board_num, self.rate)

    def configure(self, sequence) -> int:
        """Build the stimulus waveform, allocate DMA buffers, and arm the AI scan.

        Configures all digital ports as outputs, builds an interleaved
        AO+digital waveform from the decoded sequence tokens, copies it into
        the 16-bit DMA buffer, allocates the 32-bit acquisition buffer, and
        writes the trigger count register.

        Args:
            sequence: Decoded token list produced by
                ``sequence_control.decode_sequence()``.

        Returns:
            Number of detection pulses in the waveform.  The worker uses this
            to know how many trigger blocks to expect.
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