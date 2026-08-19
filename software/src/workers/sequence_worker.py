"""Acquisition worker for sequence-based (2-trigger) experiments."""

from __future__ import annotations

from config.config import config
from hardware.adc_sequence import SequenceAcquisitionADC
from hardware.adc_sequence_external import ExternalSequenceAcquisitionADC
from workers.base_worker import AcquisitionBaseWorker


class SequenceAcquisitionWorker(AcquisitionBaseWorker):
    """Worker for sequence-based acquisitions.

    Depending on ``config["General"]["hardware"]``:

    - ``"ADC"`` (default): the ADC board generates the waveform from the
      decoded sequence tokens and captures the AI data simultaneously.
    - ``"ESP32"``: the ESP32 plays the sequence and drives the LEDs/trigger
      pin; the ADC only arms a retriggered AI scan on its external trigger
      input and captures data.
    """

    def init_adc(self) -> None:
        """Shut down any existing ADC, then create and configure one for this run."""
        if self._owns_adc and self.adc and hasattr(self.adc, "shutdown"):
            self.adc.shutdown()

        self._hardware_mode = config["General"].get("hardware", "ADC")

        if self._hardware_mode == "ESP32":
            self.adc = ExternalSequenceAcquisitionADC()
            self._owns_adc = True

            self.adc.configure(self.nbr_of_points)

            # start_acquisition() resets the hardware counter to 0;
            # start_reader() must come after so it starts with last_count=0
            # and never sees stale data from the previous run.
            self.adc.start_acquisition()
            self.adc.start_reader()

            # Arm the ADC before the ESP32 starts firing triggers.
            self.esp32.send_sequence(self.sequence[4:])
        else:
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

    def _apply_background_light(self, amplitude: float) -> None:
        """Route background-light updates through the ESP32 when it owns the LEDs."""
        if self._hardware_mode == "ESP32" and self.esp32:
            self.esp32.set_background_light(amplitude)
        else:
            super()._apply_background_light(amplitude)

    def prepare_time_values(self) -> None:
        """Build a millisecond timestamp list by walking the sequence token stream.

        Tokens are interpreted as:

        - ``'D'``: a detection point — records the current time and advances by
          one analog pulse width (20 µs).
        - numeric string (no ``!`` suffix): a delay in milliseconds.
        - ``'|'``, ``'0'``, ``'1'``, ``'L'``, and ``!``-suffixed values: skipped.

        Sets ``self.time_values`` to None if the sequence is empty or produces
        no detection points.
        """
        if self.sequence is None:
            self.time_values = None
            return

        ANALOG_PULSE_WIDTH_MS = 20e-6 * 1000  # 0.02 ms

        times_ms: list[float] = []
        current_ms = 0.0

        for token in self.sequence:
            if token in ("|", "0", "1"):
                continue
            elif token == "D":
                times_ms.append(current_ms)
                current_ms += ANALOG_PULSE_WIDTH_MS
            elif token == "L":
                pass
            else:
                stripped = token.rstrip("!")
                try:
                    value = float(stripped)
                    if not token.endswith("!"):
                        current_ms += value  # delay in ms
                except ValueError:
                    pass

        self.time_values = times_ms if times_ms else None
