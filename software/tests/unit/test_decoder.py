"""Unit tests for sequence_builders.decoder.sequence_decoder."""

import pytest

from sequence_builders.decoder import sequence_decoder

pytestmark = pytest.mark.unit


@pytest.fixture
def decoder():
    return sequence_decoder()


class TestExpandParentheses:
    def test_simple_repetition(self, decoder):
        assert decoder.expand_parentheses("4(AB)") == "ABABABAB"

    def test_nested_repetition_expands_inside_out(self, decoder):
        assert decoder.expand_parentheses("2(A3(B))") == "ABBBABBB"

    def test_no_groups_returns_input_unchanged(self, decoder):
        assert decoder.expand_parentheses("ABCD") == "ABCD"


class TestDecodeSequence:
    def test_empty_string_yields_header_only(self, decoder):
        assert decoder.decode_sequence("") == ["1", "|", "0", "|"]

    def test_no_unit_defaults_to_milliseconds(self, decoder):
        assert decoder.decode_sequence("100") == ["1", "|", "0", "|", "100.0"]

    def test_seconds_unit_converts_to_milliseconds(self, decoder):
        assert decoder.decode_sequence("2s") == ["1", "|", "0", "|", "2000.0"]

    def test_explicit_milliseconds_unit(self, decoder):
        assert decoder.decode_sequence("250ms") == ["1", "|", "0", "|", "250.0"]

    def test_microseconds_unit_us(self, decoder):
        assert decoder.decode_sequence("500us") == ["1", "|", "0", "|", "0.5"]

    def test_microseconds_unit_mu(self, decoder):
        assert decoder.decode_sequence("500µs") == ["1", "|", "0", "|", "0.5"]

    def test_m_unit_multiplier_is_one(self, decoder):
        assert decoder.decode_sequence("7m") == ["1", "|", "0", "|", "7.0"]

    def test_bracket_notation_becomes_step_command(self, decoder):
        assert decoder.decode_sequence("[3]") == ["1", "|", "0", "|", "3!"]

    def test_bare_trigger_token(self, decoder):
        assert decoder.decode_sequence("T") == ["1", "|", "0", "|", "T"]

    def test_bare_letter_after_numeric_token(self, decoder):
        assert decoder.decode_sequence("100msD") == ["1", "|", "0", "|", "100.0", "D"]

    def test_whitespace_is_stripped_before_decoding(self, decoder):
        assert decoder.decode_sequence("100ms D") == decoder.decode_sequence("100msD")

    def test_repetition_group_expands_before_tokenising(self, decoder):
        assert decoder.decode_sequence("2(100msD)") == [
            "1",
            "|",
            "0",
            "|",
            "100.0",
            "D",
            "100.0",
            "D",
        ]

    def test_custom_header_values(self):
        custom = sequence_decoder(NbAcqu=5, TimeBetweenAcqu=10)
        assert custom.decode_sequence("100") == ["5", "|", "10", "|", "100.0"]
