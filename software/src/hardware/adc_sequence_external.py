"""ADC driver subclass for ESP32-driven sequence experiments.

The ESP32 generates the stimulus waveform (actinic light, detection LED
pulses, trigger pin) itself; the board only captures the photodiode response
on its AI inputs, retriggered by the ESP32's pulses on the board's external
trigger input.
"""

from mcculw import ul
from mcculw.enums import FunctionType

from hardware.adc_base import ADCBase


class ExternalSequenceAcquisitionADC(ADCBase):
    """Listen-only ADC driver for ESP32-driven sequence experiments.

    Arms a retriggered background AI scan on the board's external trigger
    input (wired to the ESP32's trigger pin) and captures the photodiode
    response. No AO/digital waveform is generated — the ESP32 owns the LEDs
    and the trigger pin.

    Typical call order::

        adc = ExternalSequenceAcquisitionADC()
        adc.configure(number_of_pulses)  # allocate acq buffer
        adc.start_reader()               # start background reader thread
        adc.start_acquisition()          # arm the AI scan
        esp32.send_sequence(...)         # ESP32 starts firing triggers
        # ... consume blocks via adc.read_block() ...
        adc.stop_acquisition()           # stop the AI scan, free buffers
    """

    def configure(self, number_of_pulses: int) -> None:
        """Allocate the acquisition buffer.

        Args:
            number_of_pulses: Number of detection pulses (``'D'`` tokens) in
                the sequence the ESP32 is about to play back.
        """
        self._total_acq_samples = (
            number_of_pulses * self.samples_per_trigger * self.nbr_of_triggers_per_sample
        )
        self._alloc_acq_buffer_32(self._total_acq_samples)

    def start_acquisition(self) -> None:
        """Arm the retriggered AI scan. No AO/digital output is started."""
        self._configure_trigger_count()
        self._start_ai_scan(self._total_acq_samples)

    def stop_acquisition(self) -> None:
        """Stop the AI scan and free buffers.

        Unlike :meth:`ADCBase.stop_acquisition`, this does not stop the
        ``DAQOFUNCTION`` background scan — it was never started here, and
        stopping it would raise from the MCC driver.
        """
        try:
            ul.stop_background(
                board_num=self.board_num, function_type=FunctionType.AIFUNCTION
            )
        finally:
            self._free_acq_buffer()
            self._free_waveform_buffer()
