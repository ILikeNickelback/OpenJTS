"""ADC driver subclass for ESP32-driven detection-LED calibration.

The ESP32 flashes the detection LED and pulses the trigger pin itself
(``CONTINUES_FLASH`` state); the board only keeps a large rolling AI buffer
armed on its external trigger input and captures the photodiode response.
"""

from mcculw import ul
from mcculw.enums import FunctionType

from hardware.adc_base import ADCBase


class ExternalCalibrationAcquisitionADC(ADCBase):
    """Listen-only ADC driver for ESP32-driven detection-LED calibration.

    Mirrors :class:`~hardware.adc_calibration.CalibrationAcquisitionADC`'s AI
    side (large rolling buffer, retriggered background scan) but never builds
    or starts an AO/digital waveform — the ESP32 owns the detection LED and
    the trigger pin.

    Attributes:
        BUFFER_SIZE_MULTIPLIER (int): Scales the acquisition buffer relative
            to ``samples_per_trigger``.
    """

    BUFFER_SIZE_MULTIPLIER = 1000

    def configure(self) -> None:
        """Allocate the rolling acquisition buffer and arm the retriggered AI scan."""
        total_buffer_points = self.samples_per_trigger * self.BUFFER_SIZE_MULTIPLIER
        self._alloc_acq_buffer_32(total_buffer_points)
        self._configure_trigger_count()
        self._start_ai_scan(total_buffer_points)

    def stop_acquisition(self) -> None:
        """Stop the AI scan and free buffers.

        Unlike :meth:`hardware.adc_calibration.CalibrationAcquisitionADC.stop_acquisition`,
        this does not stop the ``DAQOFUNCTION`` background scan — it was never
        started here, and stopping it would raise from the MCC driver.
        """
        try:
            ul.stop_background(
                board_num=self.board_num, function_type=FunctionType.AIFUNCTION
            )
        finally:
            self._free_acq_buffer()
            self._free_waveform_buffer()
