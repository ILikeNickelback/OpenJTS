"""ADC driver subclass for ESP32-driven frequency-domain experiments.

The ESP32 modulates the actinic light with a sine, fires the detection flashes
and pulses the trigger pin itself (firmware ``F`` command); the board only
captures the photodiode response on its AI inputs, paced by the ESP32's pulses
on the board's external clock input.

The pulse grid is computed here, on the host, and sent to the firmware
explicitly (first pulse time, spacing, count) so the time axis and the number
of acquired points always match what the ESP32 actually plays.
"""

import numpy as np
from loguru import logger
from mcculw import ul
from mcculw.enums import FunctionType

from config.config import config
from hardware.adc_base import ADCBase

# Must match firmware/lib/config/config.h (frequency-mode trigger timing).
ESP32_PRE_TRIGGER_SPACING_US = 60.0
ESP32_PRE_TRIGGER_LEAD_US = 7.0
ESP32_FLASH_US = 20.0

# Offset of the first active-period pulse from the sine start (as in ADC mode).
MIN_START_US = 100.0


class ExternalFrequencyAcquisitionADC(ADCBase):
    """Listen-only ADC driver for ESP32-driven frequency experiments.

    Typical call order::

        adc = ExternalFrequencyAcquisitionADC()
        n_pulses = adc.configure(frequency_config)  # pulse grid + acq buffer
        adc.start_acquisition()                      # arm the AI scan
        adc.start_reader()                           # start background reader
        esp32.send_sequence(adc.esp32_command)       # ESP32 starts the run
        # ... consume blocks via adc.read_block() ...
        adc.stop_acquisition()                       # stop the AI scan, free buffers

    Attributes:
        pulse_times_ms (list[float]): Time (ms) of each detection flash;
            populated by :meth:`configure`.
        esp32_command (str): Firmware ``F`` command for this run; populated by
            :meth:`configure`.
    """

    def __init__(self):
        super().__init__()
        self._total_acq_samples: int = 0
        self.pulse_times_ms: list[float] = []
        self.esp32_command: str = ""

    def configure(self, frequency_config: dict) -> int:
        """Compute the pulse grid, build the ESP32 command and allocate buffers.

        Uses the same keys as
        :meth:`sequence_builders.frequency_waveform_builder.FrequencyWaveformBuilder.build`.
        ``saturating_pulse_data`` is not supported in ESP32 mode and is ignored.

        Args:
            frequency_config: Frequency experiment parameters dict.

        Returns:
            Number of detection pulses (acquisition points) in the run.

        Raises:
            ValueError: If the frequency is not positive or the run contains
                no detection pulses.
        """
        freq = float(frequency_config["frequency"])
        if freq <= 0:
            raise ValueError(f"Frequency must be > 0 Hz (got {freq})")
        periods = int(frequency_config["nbr_of_periods"])
        pre_periods = int(frequency_config.get("pre_detection", 0))
        post_periods = int(frequency_config.get("post_detection", 0))
        amplitude = float(frequency_config.get("amplitude", 1.0))
        offset = float(frequency_config.get("offset", 0.0))
        background = float(frequency_config.get("background_light_data", 0) or 0)
        normal_pulses = int(
            frequency_config.get(
                "normal_pulses_per_period",
                config["Sampling"].get("normal_pulses_per_period", 10),
            )
        )
        points_before_flash = int(
            config["Sampling"].get("number_of_points_before_flash", 1)
        )

        if frequency_config.get("saturating_pulse_data"):
            logger.warning(
                "Saturating pulses are not supported in ESP32 frequency mode; ignoring them"
            )

        period_us = 1e6 / freq
        total_us = period_us * (pre_periods + periods + post_periods)
        spacing_us = round(period_us / normal_pulses, 3)

        # Same grid as ADC mode: anchored MIN_START_US after the sine start,
        # extended backwards into the pre-period and forward into the post-period.
        first_sine_pulse = pre_periods * period_us + MIN_START_US
        grid_start = first_sine_pulse - np.floor(first_sine_pulse / spacing_us) * spacing_us
        grid = np.arange(grid_start, total_us, spacing_us)

        # Keep only pulses whose pre-flash triggers start at t >= 0 and whose
        # flash ends before the run does. The result stays a contiguous grid.
        lead_us = (
            ESP32_PRE_TRIGGER_LEAD_US
            + (points_before_flash - 1) * ESP32_PRE_TRIGGER_SPACING_US
            if points_before_flash > 0
            else 0.0
        )
        grid = grid[(grid >= lead_us) & (grid + ESP32_FLASH_US <= total_us)]
        if len(grid) == 0:
            raise ValueError("Frequency configuration produces no detection pulses")

        first_us = round(float(grid[0]), 3)
        count = len(grid)
        # Rebuild from the rounded values the firmware will actually use.
        self.pulse_times_ms = (
            (first_us + np.arange(count) * spacing_us) / 1000.0
        ).tolist()

        self.esp32_command = (
            f"F{freq:.9g},{pre_periods},{periods},{post_periods},"
            f"{amplitude:.4f},{offset:.4f},{background:.4f},"
            f"{first_us:.3f},{spacing_us:.3f},{count},{points_before_flash}"
        )
        logger.debug(f"ESP32 frequency command: {self.esp32_command}")

        self.nbr_of_triggers_per_sample = 1 + points_before_flash
        self._total_acq_samples = (
            count * self.samples_per_trigger * self.nbr_of_triggers_per_sample
        )
        self._alloc_acq_buffer_32(self._total_acq_samples)

        return count

    def start_acquisition(self) -> None:
        """Arm the externally clocked AI scan. No AO/digital output is started."""
        self._start_ai_scan(self._total_acq_samples, external_clock=True)

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
