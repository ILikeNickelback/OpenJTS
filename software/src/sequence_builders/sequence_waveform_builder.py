"""Waveform builders that translate decoded ESP32 sequence token lists into DAQ output arrays.

Two classes are provided:

- :class:`SequenceWaveformBuilder` — full hardware build that produces a
  ``uint16`` interleaved array for ``daq_out_scan``.
- :class:`SequencePreviewBuilder` — hardware-free variant that produces
  normalised float arrays suitable for GUI preview without a DAQ board.

Both share the same parsing helpers (:meth:`_parse_sequence`,
:meth:`_calculate_total_time`, :meth:`_is_number`).
"""

from __future__ import annotations

import numpy as np
from mcculw.device_info import DaqDeviceInfo
from typing import List, Tuple

import matplotlib.pyplot as plt

from config.config import config


class SequenceWaveformBuilder:
    """Build a 3-channel DAQ waveform from a decoded ESP32 sequence token list.

    Consumes the pipe-delimited token list produced by
    :class:`~sequence_builders.decoder.sequence_decoder` and generates a
    ``uint16`` interleaved array ``[ch0, ch1, ch2, ch0, ch1, ch2, …]`` where:

    - **ch0** — actinic/background light level set by ``N!`` intensity tokens.
    - **ch1** — 20 µs analog detection pulses triggered by ``D`` tokens.
    - **ch2** — 10 µs digital start/end markers flanking every detection pulse.

    The token list format is::

        [NbAcqu, '|', TimeBetweenAcqu, '|', token, token, …]

    Recognised tokens:

    ========  ======================================================
    Token     Meaning
    ========  ======================================================
    ``'|'``   Header separator — skipped.
    ``'D'``   Detection event — writes analog + digital pulses.
    ``'L'``   Laser trigger — parsed but not yet implemented.
    ``'N!'``  Intensity change — sets ch0 level to N % (0–100).
    ``'N'``   Delay of N milliseconds — advances the time cursor.
    ========  ======================================================

    Typical usage::

        builder = SequenceWaveformBuilder(board_num=0, rate=100_000)
        interleaved, total_samples, n_pulses = builder.build(decoded_tokens)
        builder.plot_three_channels(interleaved, total_samples, rate=100_000)

    Attributes:
        board_num (int): MCC DAQ board index.
        rate (float): Output sample rate in Hz.
        dev_info (DaqDeviceInfo): Board capability descriptor.
        analog_pulse_width (float): Detection flash duration in seconds (20 µs).
        digital_pulse_width (float): Digital marker duration in seconds (10 µs).
        actinic_light_offset (int): DAC count offset applied to ch0 to
            compensate for LED non-linearity (from ``config["LED"]``).
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

        self.analog_pulse_width = 20e-6   # 20 µs
        self.digital_pulse_width = 10e-6  # 10 µs
        self.actinic_light_offset = config["LED"]["actinic_light_offset"]

    def build(self, sequence_str: list[str], default_actinic: float = 100.0) -> Tuple[np.ndarray, int, int]:
        """Build the interleaved waveform from a decoded sequence token list.

        Parses *sequence_str* into typed commands, allocates a ``uint16``
        interleaved array sized to the total sequence duration, then iterates
        through commands to fill all three channels:

        - ``intensity`` items set ch0 from the current position forward (later
          intensity changes overwrite earlier ones).
        - ``delay`` items advance the internal sample cursor without writing
          anything.
        - ``detection`` items write a 20 µs analog pulse on ch1 and flanking
          10 µs digital markers on ch2 at the current cursor position.

        Args:
            sequence_str: Decoded token list from
                :class:`~sequence_builders.decoder.sequence_decoder`, e.g.
                ``['1', '|', '0', '|', '100.0', 'D', '50!', '100.0', 'D']``.
            default_actinic: Initial ch0 intensity in percent (0–100) applied
                before the first ``N!`` intensity token is encountered.

        Returns:
            A 3-tuple of:

            - **interleaved** (``np.ndarray[uint16]``): Flat array of length
              ``total_samples * 3`` ready for ``daq_out_scan``.
            - **total_samples** (``int``): Number of samples per channel.
            - **digital_pulse_count** (``int``): Number of digital marker
              pulses present in ch2 (each detection event produces two —
              one start, one end — so this is roughly ``2 × n_detections``).
        """
        sequence = self._parse_sequence(sequence_str)

        total_time_ms = self._calculate_total_time(sequence)
        total_samples = int(np.ceil(total_time_ms * self.rate / 1000.0))

        interleaved = np.empty(total_samples * 3, dtype=np.uint16)
        ch0_raw = interleaved[0::3]  # Actinic/background light
        ch1_raw = interleaved[1::3]  # Analog detection pulses
        ch2_raw = interleaved[2::3]  # Digital markers

        counts_max = 65535

        ch0_raw[:] = 0
        ch1_raw[:] = 0
        ch2_raw[:] = 0

        current_sample = 0
        current_actinic = default_actinic
        digital_pulse_count = 0

        for item in sequence:
            if item['type'] == 'intensity':
                current_actinic = item['value']
                intensity_counts = int(counts_max * (0.5 + 0.5 * current_actinic / 100) - self.actinic_light_offset)
                # Applied from current position onward; overwritten by the next intensity token.
                ch0_raw[current_sample:] = intensity_counts

            elif item['type'] == 'delay':
                delay_samples = int(item['value'] * self.rate / 1000.0)
                current_sample = min(current_sample + delay_samples, total_samples)

            elif item['type'] == 'detection':
                pulse_width_samples = int(self.analog_pulse_width * self.rate)
                digital_width_samples = max(1, int(self.rate * self.digital_pulse_width))

                # Analog pulse (20 µs)
                pulse_start = current_sample
                pulse_end = min(pulse_start + pulse_width_samples, total_samples)
                ch1_raw[pulse_start:pulse_end] = counts_max

                # Digital start marker
                marker_end = min(pulse_start + digital_width_samples, total_samples)
                ch2_raw[pulse_start:marker_end] = 0xFFFF
                digital_pulse_count += 1

                # Digital end marker
                end_marker_start = pulse_end
                end_marker_end = min(end_marker_start + digital_width_samples, total_samples)
                ch2_raw[end_marker_start:end_marker_end] = 0xFFFF
                digital_pulse_count += 1

            elif item['type'] == 'laser':
                pass

        analog_pulse_count = np.count_nonzero(ch1_raw > 0)
        digital_pulse_count = int(np.count_nonzero(ch2_raw > 0) / 4)
        print(f"Analog pulses: {analog_pulse_count}")
        print(f"Total digital pulses generated: {digital_pulse_count}")

        return interleaved, total_samples, digital_pulse_count

    def _parse_sequence(self, sequence_str) -> List[dict]:
        """Parse a decoded token list into a structured command list.

        Iterates over *sequence_str* token by token, classifying each into one
        of four command types and discarding header markers (``'|'``, ``'1'``,
        ``'0'``).

        Token classification rules:

        - ``'D'`` → ``{'type': 'detection'}``
        - ``'L'`` → ``{'type': 'laser'}``
        - ``'N!'`` (numeric string ending with ``!``) → ``{'type': 'intensity', 'value': N}``
        - ``'N'`` (plain numeric string) → ``{'type': 'delay', 'value': N}``

        Args:
            sequence_str: Decoded token list or any iterable of string tokens,
                e.g. ``['1', '|', '0', '|', '100.0', 'D', '50!']``.

        Returns:
            List of command dicts, each with at minimum a ``'type'`` key and,
            for ``delay`` and ``intensity`` types, a ``'value'`` key (float).
        """
        tokens = list(sequence_str)

        sequence = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            if token in ['|', '1', '0']:
                i += 1
                continue

            if token == 'D':
                sequence.append({'type': 'detection'})
                i += 1

            elif token == 'L':
                sequence.append({'type': 'laser'})
                i += 1

            elif self._is_number(token):
                value = float(token.rstrip('!'))

                if token.endswith('!'):
                    sequence.append({'type': 'intensity', 'value': value})
                else:
                    sequence.append({'type': 'delay', 'value': value})
                i += 1
            else:
                i += 1

        return sequence

    def _calculate_total_time(self, sequence: List[dict]) -> float:
        """Sum the total waveform duration in milliseconds from a parsed sequence.

        Only ``delay`` and ``detection`` items contribute to the duration.
        Intensity changes and laser triggers are instantaneous and add no time.

        Args:
            sequence: Parsed command list produced by :meth:`_parse_sequence`.

        Returns:
            Total waveform duration in milliseconds.
        """
        total_ms = 0.0
        for item in sequence:
            if item['type'] == 'delay':
                total_ms += item['value']
            elif item['type'] == 'detection':
                total_ms += self.analog_pulse_width * 1000.0

        return total_ms

    @staticmethod
    def _is_number(s: str) -> bool:
        """Return ``True`` if *s* represents a numeric value, ignoring a trailing ``!``.

        Args:
            s: Token string to test, e.g. ``'100.0'`` or ``'50!'``.

        Returns:
            ``True`` if ``float(s.rstrip('!'))`` succeeds, ``False`` otherwise.
        """
        try:
            float(s.rstrip('!'))
            return True
        except ValueError:
            return False

    def plot_three_channels(self, interleaved: np.ndarray, total_samples: int, rate: float) -> None:
        """Open a matplotlib window showing the three output channels.

        De-interleaves *interleaved* and plots ch0 (actinic), ch1 (analog
        detection pulses), and ch2 (digital markers) as separate subplots on
        a shared time axis in seconds.

        Args:
            interleaved: Flat ``uint16`` array of length ``total_samples * 3``
                as returned by :meth:`build`.
            total_samples: Number of samples per channel, used to build the
                time axis.
            rate: Sample rate in Hz used to convert sample indices to seconds.
        """
        ch0 = interleaved[0::3]
        ch1 = interleaved[1::3]
        ch2 = interleaved[2::3]

        t = np.arange(total_samples) / rate

        plt.figure(figsize=(12, 8))

        plt.subplot(3, 1, 1)
        plt.plot(t, ch0)
        plt.title("Channel 0")
        plt.xlabel("Time (s)")
        plt.ylabel("Counts")

        plt.subplot(3, 1, 2)
        plt.plot(t, ch1)
        plt.title("Channel 1")
        plt.xlabel("Time (s)")
        plt.ylabel("Counts")

        plt.subplot(3, 1, 3)
        plt.plot(t, ch2)
        plt.title("Channel 2")
        plt.xlabel("Time (s)")
        plt.ylabel("Counts")

        plt.tight_layout()
        plt.show()


class SequencePreviewBuilder:
    """Hardware-free variant of :class:`SequenceWaveformBuilder` for GUI preview.

    Reuses the same parsing logic but replaces all ``mcculw``/``DaqDeviceInfo``
    calls with nominal values so it works without a DAQ board connected.

    Returns normalised float arrays (actinic 0–100 %, pulses 0–100) at a
    reduced ``PREVIEW_RATE`` suitable for direct plotting with DPG or
    matplotlib without allocating a full-rate DAQ buffer.

    Attributes:
        PREVIEW_RATE (float): Sample rate used for preview arrays (5 000 Hz).
            Low enough to be fast; high enough to resolve individual pulses.
        analog_pulse_width (float): Detection flash duration in seconds (20 µs),
            kept in sync with :class:`SequenceWaveformBuilder`.
        digital_pulse_width (float): Digital marker duration in seconds (10 µs).
    """

    PREVIEW_RATE        = 5000.0   # Hz — low enough to be fast, high enough to see pulses
    analog_pulse_width  = 20e-6    # seconds — matches SequenceWaveformBuilder
    digital_pulse_width = 10e-6

    def build(self, decoded_sequence: list) -> dict:
        """Build preview arrays from a decoded sequence token list.

        Parses *decoded_sequence* at :attr:`PREVIEW_RATE` and fills two
        per-sample float arrays.  A 5 % tail (minimum 20 ms) is appended so
        the final event is not clipped at the plot edge.

        Args:
            decoded_sequence: Token list produced by
                :class:`~sequence_builders.decoder.sequence_decoder`, e.g.
                ``['1', '|', '0', '|', '100.0', 'D', '100.0', 'D']``.

        Returns:
            A dict with three keys:

            - **time_ms** (``list[float]``): Sample timestamps in milliseconds.
            - **actinic** (``list[float]``): Actinic light level per sample
              (0–100 %).
            - **pulses** (``list[float]``): Detection pulse signal per sample
              (0 at rest, 100 during a pulse).

            All three lists have the same length.  An empty dict with empty
            lists is returned when the total sequence duration is zero.
        """
        parsed   = self._parse_sequence(decoded_sequence)
        total_ms = self._calculate_total_time(parsed)

        if total_ms <= 0:
            return {'time_ms': [], 'actinic': [], 'pulses': []}

        # Add a tail so the last event doesn't get clipped at the plot edge
        total_ms += max(20.0, total_ms * 0.05)

        rate          = self.PREVIEW_RATE
        total_samples = max(1, int(np.ceil(total_ms * rate / 1000.0)))
        pulse_samples = max(1, int(rate * self.analog_pulse_width))

        actinic = np.zeros(total_samples, dtype=float)
        pulses  = np.zeros(total_samples, dtype=float)

        current_sample  = 0
        current_actinic = 0.0

        for item in parsed:
            if item['type'] == 'intensity':
                current_actinic = item['value']
                actinic[current_sample:] = current_actinic

            elif item['type'] == 'delay':
                current_sample = min(
                    current_sample + int(item['value'] * rate / 1000.0),
                    total_samples - 1,
                )

            elif item['type'] == 'detection':
                end = min(current_sample + pulse_samples, total_samples)
                pulses[current_sample:end] = 100.0

        time_ms = (np.arange(total_samples) / rate * 1000.0).tolist()
        return {
            'time_ms': time_ms,
            'actinic': actinic.tolist(),
            'pulses':  pulses.tolist(),
        }

    # Reuse the stateless parsing helpers from SequenceWaveformBuilder directly
    _parse_sequence       = SequenceWaveformBuilder._parse_sequence
    _calculate_total_time = SequenceWaveformBuilder._calculate_total_time
    _is_number            = staticmethod(SequenceWaveformBuilder._is_number)


# Example usage
if __name__ == "__main__":
    builder = SequenceWaveformBuilder(board_num=0, rate=100000)

    sequence_str = ['1', '|', '0', '|', '100.0', 'D', '100.0', 'D', '100.0', 'D', '100.0', 'D', '100!', '20.0', 'A', '0!', '0.3', 'D', '1.0', 'D', '2.0', 'D', '5.0', 'D', '5.0', 'D', '5.0', 'D', '5.0', 'D', '5.0', 'D', '10.0', 'D', '10.0', 'D', '10.0', 'D', '10.0', 'D', '10.0', 'D', '20.0', 'D', '20.0', 'D', '20.0', 'D', '20.0', 'D', '20.0', 'D', '100.0', 'D', '100.0', 'D']

    waveform, total_samples, digital_count = builder.build(sequence_str)

    print(f"Total samples: {total_samples}")
    print(f"Waveform shape: {waveform.shape}")
    print(f"Duration: {total_samples / 100000 * 1000:.2f} ms")

    builder.plot_three_channels(waveform, total_samples, rate=100000)