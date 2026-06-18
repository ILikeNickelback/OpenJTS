"""Shared pytest fixtures for the OpenJTS test suite."""

import pytest


class FakeADC:
    """Minimal hardware-free stand-in for an ``ADCBase``-derived ADC.

    Exposes just enough of the real interface (``samples_per_trigger``,
    ``nbr_of_triggers_per_sample``, ``get_status``, ``read_block``,
    ``to_voltage_32``, ``stop_acquisition``, ``stop_reader``) for
    :class:`workers.base_worker.AcquisitionBaseWorker` to run its full
    command/acquisition loop without touching ``mcculw``.
    """

    def __init__(
        self,
        samples_per_trigger: int = 8,
        nbr_of_triggers_per_sample: int = 2,
        raw_block: list[int] | None = None,
    ) -> None:
        self.samples_per_trigger = samples_per_trigger
        self.nbr_of_triggers_per_sample = nbr_of_triggers_per_sample
        self._raw_block = (
            raw_block
            if raw_block is not None
            else list(range(samples_per_trigger * nbr_of_triggers_per_sample))
        )
        self.stop_acquisition_called = False
        self.stop_reader_called = False

    def get_status(self) -> int:
        return self.samples_per_trigger * self.nbr_of_triggers_per_sample

    def read_block(self) -> list[int]:
        return list(self._raw_block)

    def to_voltage_32(self, raw: int) -> float:
        return raw / 1000.0

    def stop_acquisition(self) -> None:
        self.stop_acquisition_called = True

    def stop_reader(self) -> None:
        self.stop_reader_called = True

    def shutdown(self) -> None:
        pass

    def set_background_light(self, value: float) -> None:
        pass


@pytest.fixture
def make_fake_adc():
    """Factory fixture: returns the ``FakeADC`` class for parametrized instantiation."""
    return FakeADC
