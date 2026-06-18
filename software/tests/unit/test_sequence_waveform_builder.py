"""Unit tests for the hardware-free parsing/preview path of sequence_waveform_builder.

Only :class:`SequencePreviewBuilder` is exercised here: it requires no DAQ
board (no ``DaqDeviceInfo`` probe in ``__init__``) and shares its parsing
helpers (``_parse_sequence``, ``_calculate_total_time``, ``_is_number``) with
the hardware-bound ``SequenceWaveformBuilder``, so testing it covers the same
pure logic without touching ``mcculw``.
"""

import math

import pytest

from sequence_builders.sequence_waveform_builder import SequencePreviewBuilder

pytestmark = pytest.mark.unit


@pytest.fixture
def builder():
    return SequencePreviewBuilder()


class TestIsNumber:
    def test_plain_float_string(self, builder):
        assert builder._is_number("100.0") is True

    def test_intensity_marker_strips_bang(self, builder):
        assert builder._is_number("50!") is True

    def test_non_numeric_token(self, builder):
        assert builder._is_number("D") is False

    def test_non_numeric_with_bang(self, builder):
        assert builder._is_number("abc!") is False


class TestParseSequence:
    def test_classifies_each_token_type(self, builder):
        tokens = ["1", "|", "0", "|", "100.0", "D", "50!", "20.0", "D"]
        parsed = builder._parse_sequence(tokens)
        assert parsed == [
            {"type": "delay", "value": 100.0},
            {"type": "detection"},
            {"type": "intensity", "value": 50.0},
            {"type": "delay", "value": 20.0},
            {"type": "detection"},
        ]

    def test_header_tokens_are_skipped(self, builder):
        parsed = builder._parse_sequence(["1", "|", "0", "|"])
        assert parsed == []

    def test_laser_token(self, builder):
        parsed = builder._parse_sequence(["L"])
        assert parsed == [{"type": "laser"}]


class TestCalculateTotalTime:
    def test_sums_delays_and_detection_pulse_widths(self, builder):
        parsed = [
            {"type": "delay", "value": 100.0},
            {"type": "detection"},
            {"type": "intensity", "value": 50.0},
            {"type": "delay", "value": 20.0},
            {"type": "detection"},
        ]
        total_ms = builder._calculate_total_time(parsed)
        # 100 + 20 ms of delay, plus two 20 us (0.02 ms) detection pulses.
        assert math.isclose(total_ms, 120.04)

    def test_intensity_only_contributes_no_time(self, builder):
        parsed = [{"type": "intensity", "value": 100.0}]
        assert builder._calculate_total_time(parsed) == 0.0


class TestBuild:
    def test_zero_duration_sequence_returns_empty_arrays(self, builder):
        result = builder.build(["1", "|", "0", "|"])
        assert result == {"time_ms": [], "actinic": [], "pulses": []}

    def test_single_delay_then_detection(self, builder):
        result = builder.build(["1", "|", "0", "|", "100.0", "D"])

        assert len(result["time_ms"]) == len(result["actinic"]) == len(result["pulses"])
        assert all(v == 0.0 for v in result["actinic"])

        # The detection pulse should land at the 100 ms mark (delay before it).
        pulse_indices = [i for i, v in enumerate(result["pulses"]) if v != 0.0]
        assert len(pulse_indices) == 1
        assert math.isclose(result["time_ms"][pulse_indices[0]], 100.0)

    def test_intensity_change_applies_from_current_position_onward(self, builder):
        result = builder.build(["1", "|", "0", "|", "50!", "40.0", "D"])

        assert all(v == 50.0 for v in result["actinic"])
        pulse_indices = [i for i, v in enumerate(result["pulses"]) if v != 0.0]
        assert len(pulse_indices) == 1
        assert math.isclose(result["time_ms"][pulse_indices[0]], 40.0)
