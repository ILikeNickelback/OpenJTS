"""Unit tests for utils.data_processing.substract_bassline."""

import numpy as np
import pytest

from utils.data_processing import substract_bassline

pytestmark = pytest.mark.unit


def test_subtracts_mean_of_leading_samples():
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    result = substract_bassline(data, baseline_points=2)
    np.testing.assert_allclose(result, [-0.5, 0.5, 1.5, 2.5, 3.5])


def test_single_baseline_point_zeroes_first_sample():
    data = np.array([10.0, 12.0, 14.0])
    result = substract_bassline(data, baseline_points=1)
    assert result[0] == 0.0
    np.testing.assert_allclose(result, [0.0, 2.0, 4.0])


def test_all_zero_data_stays_zero():
    data = np.zeros(5)
    result = substract_bassline(data, baseline_points=3)
    np.testing.assert_allclose(result, np.zeros(5))


def test_handles_negative_values():
    data = np.array([-5.0, -3.0, -1.0, 1.0, 3.0])
    result = substract_bassline(data, baseline_points=2)
    np.testing.assert_allclose(result, [-1.0, 1.0, 3.0, 5.0, 7.0])
