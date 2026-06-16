import numpy as np

def substract_bassline(data, baseline_points):
    baseline = np.mean(data[:baseline_points])
    return data - baseline