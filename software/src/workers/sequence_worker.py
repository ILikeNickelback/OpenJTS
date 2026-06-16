from __future__ import annotations

from hardware.adc_sequence import SequenceAcquisitionADC
from workers.worker import AcquisitionBaseWorker


class SequenceAcquisitionWorker(AcquisitionBaseWorker):
    """Worker for sequence-based acquisitions.

    The ADC board generates the waveform from the decoded sequence tokens and
    captures the AI data simultaneously.
    """

    def init_adc(self) -> None:
        if self._owns_adc and self.adc and hasattr(self.adc, "shutdown"):
            self.adc.shutdown()

        self.adc = SequenceAcquisitionADC()
        self._owns_adc = True

        # configure() builds the waveform and returns the real point count
        nbr = self.adc.configure(self.sequence)
        self.nbr_of_points = nbr

        # start_acquisition() resets the hardware counter to 0;
        # start_reader() must come after so it starts with last_count=0
        # and never sees stale data from the previous run.
        self.adc.start_acquisition()
        self.adc.start_reader()

    def prepare_time_values(self) -> None:
        if self.sequence is None:
            self.time_values = None
            return

        ANALOG_PULSE_WIDTH_MS = 20e-6 * 1000  # 0.02 ms

        times_ms: list[float] = []
        current_ms = 0.0

        for token in self.sequence:
            if token in ('|', '0', '1'):
                continue
            elif token == 'D':
                times_ms.append(current_ms)
                current_ms += ANALOG_PULSE_WIDTH_MS
            elif token == 'L':
                pass
            else:
                stripped = token.rstrip('!')
                try:
                    value = float(stripped)
                    if not token.endswith('!'):
                        current_ms += value  # delay in ms
                except ValueError:
                    pass

        self.time_values = times_ms if times_ms else None