"""Integration tests for hardware.esp32.Esp32Base with the serial layer faked.

These tests never touch a real serial port: ``serial.tools.list_ports.comports``
is monkeypatched to return synthetic port descriptors, and the "no port found"
path is used to verify Esp32Base degrades gracefully instead of raising.
"""

from types import SimpleNamespace

import pytest
import serial.tools.list_ports

from hardware.esp32 import Esp32Base

pytestmark = pytest.mark.integration


def _fake_port(description, device):
    return SimpleNamespace(description=description, device=device)


class TestFindEsp32:
    def test_matches_usb_in_description(self, monkeypatch):
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [_fake_port("Silicon Labs CP210x USB to UART Bridge", "COM5")],
        )
        assert Esp32Base.find_esp32() == "COM5"

    def test_matches_uart_in_description(self, monkeypatch):
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [_fake_port("UART Bridge Controller", "COM7")],
        )
        assert Esp32Base.find_esp32() == "COM7"

    def test_returns_none_when_no_port_matches(self, monkeypatch):
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [_fake_port("Bluetooth Link", "COM3")],
        )
        assert Esp32Base.find_esp32() is None

    def test_returns_none_when_no_ports_available(self, monkeypatch):
        monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: [])
        assert Esp32Base.find_esp32() is None

    def test_returns_first_match_among_several_ports(self, monkeypatch):
        monkeypatch.setattr(
            serial.tools.list_ports,
            "comports",
            lambda: [
                _fake_port("Bluetooth Link", "COM3"),
                _fake_port("USB Serial Device", "COM9"),
            ],
        )
        assert Esp32Base.find_esp32() == "COM9"


class TestEsp32BaseWithoutHardware:
    def test_degrades_gracefully_when_no_esp32_found(self, monkeypatch):
        monkeypatch.setattr(Esp32Base, "find_esp32", staticmethod(lambda: None))

        esp32 = Esp32Base()

        assert esp32.ser is None
        assert esp32.is_connected() is False

    def test_send_sequence_is_a_noop_when_disconnected(self, monkeypatch):
        monkeypatch.setattr(Esp32Base, "find_esp32", staticmethod(lambda: None))
        esp32 = Esp32Base()

        esp32.send_sequence(["1", "|", "0", "|", "100.0", "D"])  # must not raise

        assert esp32.is_connected() is False

    def test_disconnect_is_a_noop_when_never_connected(self, monkeypatch):
        monkeypatch.setattr(Esp32Base, "find_esp32", staticmethod(lambda: None))
        esp32 = Esp32Base()

        esp32.disconnect()  # must not raise
