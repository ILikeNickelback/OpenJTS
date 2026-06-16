from __future__ import annotations

import numpy as np

from hardware.adc_frequency import FrequencyAcquisitionADC
from workers.worker import AcquisitionBaseWorker


class FrequencyAcquisitionWorker(AcquisitionBaseWorker):
    """Worker for frequency-based acquisitions.

    Expects the configure command to carry:
        config["frequency_config"]  -- dict of frequency parameters
    and self.sequence to hold the decoded sequence.

    configure() returns the number of logical acquisition points,
    which overrides the nbr_of_points sent with the command.
    """

    def init_adc(self) -> None:
        if self._owns_adc and self.adc and hasattr(self.adc, "shutdown"):
            self.adc.shutdown()

        self.adc = FrequencyAcquisitionADC()
        self._owns_adc = True

        frequency_config = dict(self.config.get("frequency_config", {}))
        frequency_config.setdefault("background_light_data", self.config.get("background_light_data", 0))
        nbr = self.adc.configure(frequency_config)
        self.nbr_of_points = nbr  # configure() returns the real point count

        # start_acquisition() resets the hardware counter to 0;
        # start_reader() must come after so it starts with last_count=0
        # and never sees stale data from the previous run.
        self.adc.start_acquisition()
        self.adc.start_reader()

    def prepare_time_values(self) -> None:
        if self.nbr_of_points is None or self.nbr_of_points == 0:
            self.time_values = None
            return

        if hasattr(self.adc, "pulse_times_ms") and self.adc.pulse_times_ms:
            self.time_values = self.adc.pulse_times_ms
            return

        frequency_config = self.config.get("frequency_config", {})
        freq = float(frequency_config.get("frequency", 1.0))
        pre_periods = int(frequency_config.get("pre_detection", 0))
        periods = int(frequency_config.get("nbr_of_periods", 1))
        post_periods = int(frequency_config.get("post_detection", 0))
        total_periods = pre_periods + periods + post_periods

        total_duration_ms = total_periods * 1000.0 / freq
        self.time_values = np.linspace(0, total_duration_ms, self.nbr_of_points, endpoint=False).tolist()
