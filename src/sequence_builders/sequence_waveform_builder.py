from __future__ import annotations
import numpy as np
from mcculw import ul
from mcculw.device_info import DaqDeviceInfo
from typing import List, Tuple


import matplotlib.pyplot as plt
import numpy as np

from config.config import config

class SequenceWaveformBuilder:
    """Build DAQ waveform from ESP32 sequence string.
    
    Parses sequences like: ['1', '|', '0', '|', '100.0', 'D', '100.0', 'D', ...]
    and generates corresponding 3-channel interleaved waveform for DAQ output.
    """

    def __init__(self, board_num: int, rate: float):
        """
        Args:
            board_num: DAQ board number
            rate: Sampling rate in Hz (e.g., 100000 for 100kHz)
        """
        self.board_num = board_num
        self.rate = rate
        self.dev_info = DaqDeviceInfo(self.board_num)
        
        # Pulse widths in seconds
        self.analog_pulse_width = 20e-6  # 20 microseconds
        self.digital_pulse_width = 10e-6  # 10 microseconds
        self.actinic_light_offset = config["LED"]["actinic_light_offset"]

    def build(self, sequence_str: str, default_actinic: float = 100.0) -> Tuple[np.ndarray, int, int]:
        """Build waveform from sequence string.
        
        Args:
            sequence_str: ESP32 sequence string
            default_actinic: Default actinic light intensity (0-100%)
            
        Returns:
            Tuple of (interleaved_waveform, total_samples, digital_pulse_count)
        """
        # Parse sequence string
        sequence = self._parse_sequence(sequence_str)
        
        # Calculate total time and samples needed
        total_time_ms = self._calculate_total_time(sequence)
        total_samples = int(np.ceil(total_time_ms * self.rate / 1000.0))
        
        # Pre-allocate interleaved array
        interleaved = np.empty(total_samples * 3, dtype=np.uint16)
        ch0_raw = interleaved[0::3]  # Actinic/background light
        ch1_raw = interleaved[1::3]  # Analog detection pulses
        ch2_raw = interleaved[2::3]  # Digital markers
        
        # Initialize channels
        ao_info = self.dev_info.get_ao_info()
        ao_range = ao_info.supported_ranges[0]
        
        counts_max = 65535
        pulse_counts = ul.from_eng_units(self.board_num, ao_range, 10)  # 1V pulse
        
        ch0_raw[:] = 0
        ch1_raw[:] = 0
        ch2_raw[:] = 0
        
        # Process sequence and fill channels
        current_sample = 0
        current_actinic = default_actinic
        digital_pulse_count = 0
        
        for item in sequence:
            if item['type'] == 'intensity':
                # Set actinic light intensity
                current_actinic = item['value']
                intensity_counts = int(counts_max * (0.5 + 0.5 * current_actinic / 100) - self.actinic_light_offset)
                # Apply from current position onward (will be overwritten by next intensity change)
                ch0_raw[current_sample:] = intensity_counts
                
            elif item['type'] == 'delay':
                # Advance time
                delay_samples = int(item['value'] * self.rate / 1000.0)
                current_sample = min(current_sample + delay_samples, total_samples)
                
            elif item['type'] == 'detection':
                # Add detection pulse to ch1 (analog) and ch2 (digital markers)
                pulse_width_samples = int(self.analog_pulse_width * self.rate)
                digital_width_samples = max(1, int(self.rate * self.digital_pulse_width))
                
                # Analog pulse (20µs)
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
                # Optional: handle laser trigger if needed
                pass
        
        analog_pulse_count = np.count_nonzero(ch1_raw > 0)
        digital_pulse_count = int(np.count_nonzero(ch2_raw > 0) / 4)
        print(f"Analog pulses: {analog_pulse_count}")
        print(f"Total digital pulses generated: {digital_pulse_count}")
        
        return interleaved, total_samples, digital_pulse_count

    def _parse_sequence(self, sequence_str) -> List[dict]:
        """Parse sequence string into structured commands.
        
        Returns:
            List of dicts with 'type' and 'value' keys
        """
        # Remove brackets and quotes, split by comma
        tokens = list(sequence_str)
        
        sequence = []
        i = 0
        
        while i < len(tokens):
            token = tokens[i]
            
            # Skip header markers
            if token in ['|', '1', '0']:
                i += 1
                continue
            
            # Detection trigger
            if token == 'D':
                sequence.append({'type': 'detection'})
                i += 1
                
            # Laser trigger
            elif token == 'L':
                sequence.append({'type': 'laser'})
                i += 1
                
            # Number (could be intensity or delay)
            elif self._is_number(token):
                value = float(token.rstrip('!'))
                
                # Intensity setting (ends with !)
                if token.endswith('!'):
                    sequence.append({'type': 'intensity', 'value': value})
                # Delay in milliseconds
                else:
                    sequence.append({'type': 'delay', 'value': value})
                i += 1
            else:
                i += 1
        
        return sequence
    
    def _calculate_total_time(self, sequence: List[dict]) -> float:
        """Calculate total time in milliseconds from sequence.
        
        Args:
            sequence: Parsed sequence list
            
        Returns:
            Total time in milliseconds
        """
        total_ms = 0.0
        for item in sequence:
            if item['type'] == 'delay':
                total_ms += item['value']
            elif item['type'] == 'detection':
                # Add detection pulse duration
                total_ms += self.analog_pulse_width * 1000.0
        
        return total_ms
    
    @staticmethod
    def _is_number(s: str) -> bool:
        """Check if string represents a number."""
        try:
            float(s.rstrip('!'))
            return True
        except ValueError:
            return False

    def plot_three_channels(self, interleaved: np.ndarray, total_samples: int, rate: float) -> None:
        # De-interleave
        ch0 = interleaved[0::3]
        ch1 = interleaved[1::3]
        ch2 = interleaved[2::3]

        # Time axis (per channel)
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
    """Hardware-free version of SequenceWaveformBuilder for visualization.

    Reuses the same parsing logic but replaces all mcculw/DaqDeviceInfo calls
    with nominal values so it works without a DAQ board connected.

    Returns normalised float arrays (actinic 0-100 %, pulses 0-100) suitable
    for direct plotting with DPG.
    """

    PREVIEW_RATE        = 5000.0   # Hz — low enough to be fast, high enough to see pulses
    analog_pulse_width  = 20e-6    # seconds — matches SequenceWaveformBuilder
    digital_pulse_width = 10e-6

    def build(self, decoded_sequence: list) -> dict:
        """Build preview arrays from a decoded sequence token list.

        Args:
            decoded_sequence: token list produced by sequence_decoder,
                              e.g. ['1','|','0','|','100.0','D','100.0','D',...]

        Returns:
            dict with keys:
                time_ms  – list[float] timestamps in milliseconds
                actinic  – list[float] actinic light level  (0 – 100 %)
                pulses   – list[float] detection pulses      (0 – 100, pulse = 100)
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
    
    # Your example sequence
    sequence_str = ['1', '|', '0', '|', '100.0', 'D', '100.0', 'D', '100.0', 'D', '100.0', 'D', '100!', '20.0', 'A', '0!', '0.3', 'D', '1.0', 'D', '2.0', 'D', '5.0', 'D', '5.0', 'D', '5.0', 'D', '5.0', 'D', '5.0', 'D', '10.0', 'D', '10.0', 'D', '10.0', 'D', '10.0', 'D', '10.0', 'D', '20.0', 'D', '20.0', 'D', '20.0', 'D', '20.0', 'D', '20.0', 'D', '100.0', 'D', '100.0', 'D']
    
    waveform, total_samples, digital_count = builder.build(sequence_str)
    
    print(f"Total samples: {total_samples}")
    print(f"Waveform shape: {waveform.shape}")
    print(f"Duration: {total_samples / 100000 * 1000:.2f} ms")
    
    builder.plot_three_channels(waveform, total_samples, rate=100000)