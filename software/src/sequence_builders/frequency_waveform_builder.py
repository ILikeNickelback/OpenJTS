"""Interleaved 3-channel waveform builder for frequency-modulated LED acquisitions.

Produces a ``uint16`` interleaved array driving AO channels 0–1 and one digital
channel via ``daq_out_scan``.  The resulting waveform encodes a sine-wave
actinic background (ch0), evenly-spaced analog detection flashes (ch1), and
the corresponding digital acquisition triggers (ch2).
"""

from __future__ import annotations

import numpy as np
from mcculw.device_info import DaqDeviceInfo
from config.config import config
import matplotlib.pyplot as plt


class FrequencyWaveformBuilder:
    """Build the interleaved 3-channel waveform used by ``FrequencyAcquisitionADC``.

    Produces a ``numpy.uint16`` interleaved array
    ``[ch0, ch1, ch2, ch0, ch1, ch2, …]`` where:

    - **ch0** — sinusoidal actinic light, clamped to background level during
      pre/post periods and saturated during override windows.
    - **ch1** — 20 µs analog detection flashes at a global evenly-spaced grid,
      replaced by denser override pulses inside saturating windows.
    - **ch2** — digital acquisition markers: ``points_before_flash`` pre-pulses
      plus one during-pulse around each ch1 flash.

    After :meth:`build` returns, ``self.pulse_times_ms`` holds the time of
    every digital trigger event (in ms), which callers use to build the
    measurement time axis.

    Typical usage::

        builder = FrequencyWaveformBuilder(board_num, rate)
        interleaved, total_samples, n_pulses = builder.build(frequency_config)
        times_ms = builder.pulse_times_ms

    Attributes:
        board_num (int): MCC DAQ board index.
        rate (float): Output sample rate in Hz.
        dev_info (DaqDeviceInfo): Board capability descriptor used to query the
            AO voltage range.
        points_before_flash (int): Number of digital pre-pulses written before
            each analog flash (from ``config["Sampling"]``).
        counts_max (int): Full-scale DAC count value (65535 for 16-bit).
        dark_window (int): Extra samples cleared on each side of a saturating
            flash to ensure the detector is unlit during acquisition.
        actinic_light_offset (int): DAC count offset applied to ch0 to
            compensate for LED non-linearity (from ``config["LED"]``).
        pulse_times_ms (list[float]): Populated by :meth:`build` — the time in
            ms of each digital trigger event, excluding the final boundary
            point.
    """

    def __init__(self, board_num: int, rate: float) -> None:
        """Initialise the builder, probe the DAQ board, and load config values.

        Args:
            board_num: MCC DAQ board index passed to ``DaqDeviceInfo``.
            rate: Output sample rate in Hz used for all timing calculations.
        """
        self.board_num = board_num
        self.rate = rate
        self.dev_info = DaqDeviceInfo(self.board_num)
        self.points_before_flash = config["Sampling"].get("number_of_points_before_flash", 1)
        self.counts_max = 65535
        self.dark_window = 120
        self.actinic_light_offset = config["LED"]["actinic_light_offset"]
        self.pulse_times_ms: list[float] = []

    def build(self, frequency_config: dict) -> tuple[np.ndarray, int, int]:
        """Build the full interleaved waveform for a frequency-sweep acquisition.

        Constructs all three channels in a single pre-allocated ``uint16``
        array.  Saturating-pulse windows override both the actinic sine (ch0)
        and the normal flash grid (ch1/ch2) with denser pulses and a dark
        blanking window.

        The method also populates ``self.pulse_times_ms`` as a side effect —
        callers that need the time axis should read it after this call returns.

        Required keys in *frequency_config*:

        - ``"frequency"`` (float): Actinic modulation frequency in Hz.
        - ``"nbr_of_periods"`` (int): Number of active (sine-wave) periods.

        Optional keys in *frequency_config*:

        - ``"pre_detection"`` (int, default 0): Silent periods before the sine.
        - ``"post_detection"`` (int, default 0): Silent periods after the sine.
        - ``"background_light_data"`` (float, default 0): Background intensity
          (% of full scale) used to phase the sine and fill dead periods.
        - ``"amplitude"`` (float, default 1.0): Sine amplitude in % of full scale.
        - ``"offset"`` (float, default 0.0): Sine DC offset in % of full scale.
        - ``"normal_pulses_per_period"`` (int): Flash count per period; falls
          back to ``config["Sampling"]["normal_pulses_per_period"]`` (default 10).
        - ``"saturating_pulse_data"`` (dict | None): Mapping of override windows.
          Each value must contain ``"period_number"``, ``"degree"``, and
          ``"duration_ms"``.

        Args:
            frequency_config: Configuration dict for this acquisition (see above).

        Returns:
            A 3-tuple of:

            - **interleaved** (``np.ndarray[uint16]``): Flat array of length
              ``total_samples * 3`` ready for ``daq_out_scan``.
            - **total_samples** (``int``): Number of samples per channel across
              all periods (pre + active + post).
            - **length** (``int``): Number of digital trigger events emitted
              (equals ``len(self.pulse_times_ms)``).
        """
        ao_info = self.dev_info.get_ao_info()
        ao_range = ao_info.supported_ranges[0]

        freq = float(frequency_config["frequency"])
        periods = int(frequency_config["nbr_of_periods"])
        pre_periods = int(frequency_config.get("pre_detection", 0))
        post_periods = int(frequency_config.get("post_detection", 0))
        saturating_pulse_data = frequency_config.get("saturating_pulse_data", None)
        background_light_data = frequency_config.get("background_light_data", 0)

        samples_per_period = int(self.rate / freq)
        total_periods = pre_periods + periods + post_periods
        total_samples = samples_per_period * total_periods
        pulse_width_samples = int(self.rate * 20e-6)  # 20 µs

        normal_pulses = frequency_config.get("normal_pulses_per_period", config["Sampling"].get("normal_pulses_per_period", 10))

        # ---- Precompute saturating-pulse windows and the flash pulses inside them ----
        saturating_overrides = []
        if saturating_pulse_data:
            override_pulses = config["Sampling"].get("override_pulses", 4)
            for p in saturating_pulse_data.values():
                start = int((p["period_number"] + p["degree"] / 360) * samples_per_period)
                end = int(start + p["duration_ms"] * self.rate / 1000)
                pulse_positions = np.linspace(2, end - start - 2, override_pulses, endpoint=False, dtype=int)
                saturating_overrides.append({"start": start, "end": end, "pulse_positions": pulse_positions})

        # Pre-allocate interleaved array and create views for each channel
        interleaved = np.empty(total_samples * 3, dtype=np.uint16)
        ch0_raw = interleaved[0::3]
        ch1_raw = interleaved[1::3]
        ch2_raw = interleaved[2::3]

        # ---- Channel 0: Sine wave with overrides ----
        t = np.arange(total_samples) / self.rate
        amplitude = frequency_config.get("amplitude", 1.0)
        offset_val = frequency_config.get("offset", 0.0)

        # Phase so the sine starts at background_light_data intensity
        if amplitude != 0:
            bg_norm = np.clip((background_light_data - offset_val) / amplitude, -1.0, 1.0)
            phase = np.arcsin(bg_norm)
        else:
            phase = 0

        sine = amplitude * np.sin(2 * np.pi * freq * t + phase) + offset_val

        counts_max = 65535
        ch0_volts = counts_max * (0.5 + 0.5 * sine / 100) - self.actinic_light_offset  # convert to counts

        background_light_data = counts_max * (0.5 + 0.5 * background_light_data / 100) - self.actinic_light_offset
        # Zero out pre/post periods
        if pre_periods > 0:
            ch0_volts[:pre_periods * samples_per_period] = background_light_data
        if post_periods > 0:
            ch0_volts[-post_periods * samples_per_period:] = background_light_data

        # Apply override pulses on ch0
        for ov in saturating_overrides:
            start, end = ov["start"], ov["end"]
            ch0_volts[start:end] = counts_max * int(ao_range.range_max / 10)
            # Saturating light off during the analog/digital flash pulses
            for offset in ov["pulse_positions"]:
                pulse_start = start + offset - self.dark_window
                pulse_end = min(pulse_start + pulse_width_samples, end) + self.dark_window
                ch0_volts[pulse_start:pulse_end] = 0

        ch0_raw[:] = ch0_volts

        # ---- Compute global evenly-spaced pulse grid ----
        # Anchor the grid to (sine_start + min_start_samples) so no pulse straddles
        # the pre-period / sine-wave boundary, then extend the same grid backward
        # into the pre-period and forward into the post-period.
        min_start_samples = int(self.rate * 100e-6)   # 100 µs offset from sine start

        sine_start = pre_periods * samples_per_period
        spacing = samples_per_period / normal_pulses   # uniform inter-pulse gap (samples)
        first_sine_pulse = sine_start + min_start_samples

        # Step the grid back so it covers the pre-period too
        n_back = int(np.floor(first_sine_pulse / spacing))
        grid_start = first_sine_pulse - n_back * spacing
        all_positions = np.arange(grid_start, total_samples, spacing).astype(int)
        all_positions = all_positions[(all_positions >= 0) & (all_positions < total_samples)]

        # ---- Channel 1: Analog pulses ----
        pulse_counts = counts_max
        ch1_raw[:] = 0
        all_positions += 4
        for pos in all_positions:
            pulse_end = min(pos + pulse_width_samples, total_samples)
            ch1_raw[pos:pulse_end] = counts_max

        length = len(all_positions)

        # Override periods (ch1)
        for ov in saturating_overrides:
            start, end = ov["start"], ov["end"]
            pulse_positions = ov["pulse_positions"]
            cleared_normals = int(np.count_nonzero(ch1_raw[start:end] > 0) / pulse_width_samples)
            ch1_raw[start:end] = 0

            for offset in pulse_positions:
                pulse_start = start + offset
                pulse_end = min(pulse_start + pulse_width_samples, end)
                ch1_raw[pulse_start:pulse_end] = pulse_counts

            length = length - cleared_normals + len(pulse_positions)

        print(f"analog pulses {length}")

        # ---- Channel 2: Digital markers ----
        ch2_raw[:] = 0
        digital_pulse_width = max(1, int(self.rate * 10e-6))

        # Skip the first normal pulse after each saturating override ends
        skip_positions = set()
        for ov in saturating_overrides:
            idx = np.searchsorted(all_positions, ov["end"])
            if idx < len(all_positions):
                skip_positions.add(all_positions[idx])

        for pos in all_positions:
            if pos in skip_positions:
                continue
            pulse_end = min(pos + pulse_width_samples, total_samples)
            self.write_pulse_markers(
                ch2_raw, pos, pulse_end,
                digital_pulse_width,
                self.rate
            )

        # Override periods (ch2)
        for ov in saturating_overrides:
            start, end = ov["start"], ov["end"]
            ch2_raw[start:end] = 0

            pulse_positions = ov["pulse_positions"]
            for offset in pulse_positions[1:]:  # ignore the first point of the saturating pulse
                pulse_start = start + offset
                pulse_end = min(pulse_start + pulse_width_samples, end)
                self.write_pulse_markers(
                    ch2_raw, pulse_start, pulse_end,
                    digital_pulse_width,
                    self.rate
                )

        # Collect actual flash-event sample positions for the time axis.
        # These are the positions that receive ch2 digital triggers (which drive ADC acquisition).
        # Normal positions outside override windows and not in skip_positions;
        # plus saturating-pulse positions (pulse_positions[1:] per override).
        flash_positions = []
        for pos in all_positions:
            if pos in skip_positions:
                continue
            if any(ov["start"] <= pos < ov["end"] for ov in saturating_overrides):
                continue
            flash_positions.append(int(pos))
        for ov in saturating_overrides:
            for offset in ov["pulse_positions"][1:]:
                flash_positions.append(int(ov["start"] + offset))
        flash_positions.sort()
        # Drop the last position (unreliable boundary point) and derive length from
        # the same set so nbr_of_points always equals len(pulse_times_ms).
        self.pulse_times_ms = [p / self.rate * 1000.0 for p in flash_positions[:-1]]
        length = len(self.pulse_times_ms)
        print(f"Total digital pulses generated: {length}")

        return interleaved, total_samples, length

    def write_pulse_markers(
        self,
        ch2_raw: np.ndarray,
        pulse_start: int,
        pulse_end: int,
        digital_pulse_width: int,
        rate: float,
    ) -> None:
        """Write digital acquisition markers around a single analog flash.

        Places ``self.points_before_flash`` evenly-spaced pre-pulses immediately
        before the analog pulse, then one during-pulse at the very start of the
        flash.  All pulses are written at full scale (``self.counts_max``).

        Pre-pulse spacing is 5 µs (``inter_pulse_gap``).  The last pre-pulse
        ends flush with *pulse_start*; earlier ones step back by
        ``inter_pulse_gap`` each.  Pre-pulses that would start before sample 0
        are silently skipped.

        The during-pulse starts 3 samples into the analog flash and is clamped
        to end no later than *pulse_end*.  A warning is printed if
        *pulse_end* is so short that the during-pulse falls entirely outside
        the flash window.

        Args:
            ch2_raw: Digital channel view of the interleaved array, modified
                in place.
            pulse_start: Sample index where the analog flash starts.
            pulse_end: Sample index where the analog flash ends (exclusive).
            digital_pulse_width: Width in samples of each digital marker pulse
                (typically 10 µs × rate).
            rate: Output sample rate in Hz, used to compute ``inter_pulse_gap``.
        """
        inter_pulse_gap = int(rate * 5 * 10e-6)   # 5 µs spacing between pulses

        # ---- points_before_flash pre-pulses BEFORE the analog pulse ----
        # Last pre-pulse ends flush at pulse_start; earlier ones step back by inter_pulse_gap
        for i in range(self.points_before_flash):
            p_end = pulse_start - (self.points_before_flash - 1 - i) * inter_pulse_gap
            p_start = p_end - digital_pulse_width
            if p_start >= 0:
                ch2_raw[p_start:p_end] = self.counts_max

        # ---- 1 pulse DURING the analog pulse ----
        during_start = pulse_start + 3
        during_end = min(during_start + digital_pulse_width, pulse_end)
        ch2_raw[during_start:during_end] = self.counts_max
        if during_start >= pulse_end:
            print(f"WARNING: during-pulse is outside analog pulse! during_start={during_start}, pulse_end={pulse_end}")

    def plot(self, frequency_config: dict) -> None:
        """Open a matplotlib window showing the three output channels.

        Calls :meth:`build` with *frequency_config* and plots ch0 (actinic
        sine), ch1 (analog flashes), and ch2 (detection markers) on a shared
        time axis in milliseconds.  Pre- and post-detection dead zones are
        shaded grey when ``"pre_detection"`` or ``"post_detection"`` keys are
        present in *frequency_config*.

        Args:
            frequency_config: Dict passed directly to :meth:`build`.  Must
                contain ``"frequency"`` (Hz).  Optionally ``"nbr_of_periods"``,
                ``"pre_detection"``, and ``"post_detection"`` control the title
                and grey shading.
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