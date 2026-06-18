# pylint: skip-file


import serial
import time
import serial.tools.list_ports
from config.config import config


class Esp32Base:
    """Handles serial communication with the ESP32."""

    def __init__(self, baud_rate=None, timeout=None):
        self.baud_rate = baud_rate or config["ESP32"]["baud_rate"]
        self.timeout = timeout or config["ESP32"]["timeout"]
        self.ser = None
        self.connect()

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    def connect(self):
        """Find the ESP32 and open the serial connection."""
        port = self.find_esp32()
        if port is None:
            self.ser = None
            return
        try:
            self.ser = serial.Serial(
                port=port, baudrate=self.baud_rate, timeout=self.timeout
            )
            time.sleep(2)  # Required: ESP32 resets on serial open
            print(f"Connected to ESP32 on {port}")
        except serial.SerialException:
            self.ser = None

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("ESP32 serial connection closed")

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def send_sequence(self, sequence):
        """Send a sequence of characters wrapped in < ... >."""
        if not self.is_connected():
            return

        try:
            if self.ser is not None:
                self.ser.write(b"<")
                for item in sequence:
                    self.ser.write(item.encode())
                    time.sleep(0.001)
                self.ser.write(b">")
        except serial.SerialException:
            return

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------
    @staticmethod
    def find_esp32():
        """Return the serial port of the ESP32 or None."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "USB" in port.description or "UART" in port.description:
                print(f"Found ESP32 on port: {port.device}")
                return port.device
        return None
