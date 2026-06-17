"""Signal processing utilities."""

import numpy as np

def substract_bassline(data, baseline_points):
    """Subtract a baseline from data.

    Computes the baseline as the mean of the first `baseline_points` samples
    and subtracts it from the entire array.

    Args:
        data (np.ndarray): 1D array of signal data.
        baseline_points (int): Number of leading samples used to compute the baseline.

    Returns:
        np.ndarray: Baseline-corrected data array.
    """
    baseline = np.mean(data[:baseline_points])
    return data - baseline
