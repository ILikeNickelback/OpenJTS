
import matplotlib.pyplot as plt
import numpy as np


def plot_three_channels(self, interleaved: np.ndarray, total_samples: int, rate: float) -> None:
    """Plot the three interleaved channels contained in the waveform.

    Parameters
    ----------
    interleaved : np.ndarray
        Interleaved array [ch0, ch1, ch2, ch0, ch1, ch2, ...]
    total_samples : int
        Number of samples per channel
    rate : float
        Sampling rate in Hz
    """
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
