"""Unit tests for sequence_builders.control.sequence_control."""

import pytest

from sequence_builders.control import sequence_control

pytestmark = pytest.mark.unit


@pytest.fixture
def control():
    return sequence_control()


class TestCountNbrOfPoints:
    def test_counts_d_characters_in_string(self, control):
        assert control.count_nbr_of_points("DDD") == 3

    def test_counts_d_tokens_in_decoded_list(self, control):
        decoded = ["1", "|", "0", "|", "100.0", "D", "100.0", "D"]
        assert control.count_nbr_of_points(decoded) == 2

    def test_returns_zero_when_no_detections(self, control):
        assert control.count_nbr_of_points("ABC") == 0


class TestDecodeSequence:
    def test_delegates_to_decoder_and_counts_points(self, control):
        decoded, nbr_of_points = control.decode_sequence("2(100msD)")
        assert decoded == ["1", "|", "0", "|", "100.0", "D", "100.0", "D"]
        assert nbr_of_points == 2
