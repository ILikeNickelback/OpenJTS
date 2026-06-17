"""Single-period calibration waveform builder for the detection LED.

Produces a 3-channel interleaved ``uint16`` array that drives AO channels 0–1
and one digital channel via ``daq_out_scan`` in ``CONTINUOUS`` mode, looping
the waveform indefinitely until the caller stops the scan.
"""

from __future__ import annotations

import numpy as np
from mcculw.device_info import DaqDeviceInfo
import matplotlib.pyplot as plt

from config.config import config


class CalibrationWaveformBuilder:
    """Build a single-period calibration waveform meant to loop continuously.

    Produces a 3-channel interleaved array ``[ch0, ch1, ch2, ch0, ch1, ch2, …]``
    where:

    - **ch0** — actinic light (always 0; calibration uses no background light)
    - **ch1** — analog detection pulses (N evenly-spaced pulses per period)
    - **ch2** — digital markers (start + end flanking every analog pulse)

    The buffer represents exactly one period of the flash pattern.  Pass it to
    ``daq_out_scan`` with ``ScanOptions.CONTINUOUS`` so the hardware loops
    until explicitly stopped.

    Typical usage::

        builder = CalibrationWaveformBuilder(board_num, rate)
        interleaved, samples_per_period, pulses_per_period = builder.build(
            config["Calibration"], intensity=80.0
        )

    Attributes:
        board_num (int): MCC DAQ board index.
        rate (float): Output sample rate in Hz.
        dev_info (DaqDeviceInfo | None): Board capability descriptor, or
            ``None`` when the board is unavailable (e.g. in unit tests).
    """

    def __init__(self, board_num: int, rate: float) -> None:
        """Initialise the builder and probe the DAQ board.

        Args:
            board_num: MCC DAQ board index passed to ``DaqDeviceInfo``.
            rate: Output sample rate in Hz used for all timing calculations.
        """
        self.board_num = board_num
        self.rate = rate
        try:
            self.dev_info = DaqDeviceInfo(self.board_num)
        except Exception:
            self.dev_info = None

    def build(self, calibration_config: dict, intensity: float = 100.0) -> tuple[np.ndarray, int, int]:
        """Build the interleaved waveform for one calibration period.

        Reads ``frequency`` and ``normal_pulses_per_period`` from
        *calibration_config*, falling back to ``config["Sampling"]`` for the
        pulse count if the key is absent.  Pulse positions are evenly spaced
        across the period starting at sample 4.

        Args:
            calibration_config: Dict containing at minimum ``"frequency"`` (Hz).
                Optional key ``"normal_pulses_per_period"`` overrides the
                global sampling default.
            intensity: Detection LED intensity as a percentage (0–100).
                Values outside this range are clamped.

        Returns:
            A 3-tuple of:
            - **interleaved** (``np.ndarray[uint16]``): Flat array of length
              ``samples_per_period * 3`` ready for ``daq_out_scan``.
            - **samples_per_period** (``int``): Number of samples per channel
              per period (``rate / frequency``).
            - **pulses_per_period** (``int``): Number of analog pulses placed
              in the period.

        Raises:
            ValueError: If *frequency* is zero or negative.
        """
        freq              = float(calibration_config.get("frequency", 1.0))
        pulses_per_period = int(calibration_config.get("normal_pulses_per_period",
                                config["Sampling"].get("normal_pulses_per_period", 10)))

        if freq <= 0:
            raise ValueError(f"Calibration frequency must be > 0 Hz (got {freq})")

        samples_per_period = int(self.rate / freq)

        interleaved = np.zeros(samples_per_period * 3, dtype=np.uint16)
        ch1_raw = interleaved[1::3]   # analog detection pulses
        ch2_raw = interleaved[2::3]   # digital markers

        counts_max          = 65535
        pulse_amplitude     = int(counts_max * max(0.0, min(100.0, intensity)) / 100.0)
        pulse_width_samples = max(1, int(self.rate * 20e-6))
        digital_width       = max(1, int(self.rate * 10e-6))

        positions = np.linspace(4, samples_per_period, pulses_per_period,
                                endpoint=False, dtype=int)

        for pos in positions:
            pulse_end = min(int(pos) + pulse_width_samples, samples_per_period)

            ch1_raw[pos+1:pulse_end+1] = pulse_amplitude

            d_start_end = min(int(pos) + digital_width, samples_per_period)
            ch2_raw[pos:d_start_end] = 0xFFFF

            d_end_start = pulse_end
            d_end_end   = min(d_end_start + digital_width, samples_per_period)
            if d_end_start < samples_per_period:
                ch2_raw[d_end_start:d_end_end] = 0xFFFF

        return interleaved, samples_per_period, pulses_per_period

    def plot(self, frequency_config: dict) -> None:
        """Open a matplotlib window showing the three output channels.

        Calls :meth:`build` with *frequency_config* and plots ch0 (actinic),
        ch1 (analog flashes), and ch2 (detection markers) on a shared time
        axis.  Pre- and post-detection dead zones are shaded grey when
        ``"pre_detection"`` or ``"post_detection"`` keys are present in
        *frequency_config*.

        Args:
            frequency_config: Dict passed directly to :meth:`build`.  Should
                contain ``"frequency"`` (Hz) and optionally
                ``"pre_detection"`` and ``"post_detection"`` (period counts)
                for dead-zone shading.
        """
        interleaved, total_samples, _ = self.build(frequency_config)
        ch0 = interleaved[0::3]
        ch1 = interleaved[1::3]
        ch2 = interleaved[2::3]

        t_ms = np.arange(total_samples) / self.rate * 1000  # ms

        fig, axes = plt.subplots(3, 1, figsize=(14, 7), sharex=True)
        fig.suptitle(
            f"Waveform preview  —  {frequency_config.get('frequency', '?')} Hz  "
            f"|  {frequency_config.get('nbr_of_periods', '?')} periods  "
            f"|  rate {self.rate/1e3:.0f} kHz",
            fontsize=11,
        )

        axes[0].plot(t_ms, ch0, linewidth=0.6, color="royalblue")
        axes[0].set_ylabel("counts")
        axes[0].set_title("Ch0 — actinic light")

        axes[1].plot(t_ms, ch1, linewidth=0.6, color="darkorange")
        axes[1].set_ylabel("counts")
        axes[1].set_title("Ch1 — analog flashes")

        axes[2].plot(t_ms, ch2, linewidth=0.6, color="seagreen")
        axes[2].set_ylabel("counts")
        axes[2].set_title("Ch2 — detection markers")
        axes[2].set_xlabel("Time (ms)")

        freq = float(frequency_config["frequency"])
        pre_periods = int(frequency_config.get("pre_detection", 0))
        post_periods = int(frequency_config.get("post_detection", 0))
        samples_per_period = int(self.rate / freq)
        pre_end_ms = pre_periods * samples_per_period / self.rate * 1000
        post_start_ms = (total_samples - post_periods * samples_per_period) / self.rate * 1000
        for ax in axes:
            if pre_periods > 0:
                ax.axvspan(0, pre_end_ms, color="grey", alpha=0.15, label="pre")
            if post_periods > 0:
                ax.axvspan(post_start_ms, t_ms[-1], color="grey", alpha=0.15, label="post")

        fig.tight_layout()
        plt.show()
