"""Shared pytest fixtures for the OpenJTS test suite."""

import sys
import types

import pytest


def _install_mcculw_hardware_stub() -> None:
    """Stub out mcculw.ul / mcculw.device_info before any app code imports them.

    The real ``mcculw.ul`` module loads Measurement Computing's native
    ``cbw64.dll`` driver as an *import-time* side effect. That DLL only
    exists on machines with their InstaCal/DAQ driver installed -- not CI
    runners, and not guaranteed on every contributor's machine. None of these
    tests call real mcculw functions (hardware is faked at a higher level:
    ``FakeADC``, mocked ``serial``), so importing the real, DLL-backed module
    is both unnecessary and unreliable. Installing a stub keeps the whole
    suite hermetic regardless of what's installed on the host.
    """
    import mcculw  # the real top-level package; trivial, no DLL side effect

    if isinstance(getattr(mcculw, "ul", None), types.ModuleType) and hasattr(
        sys.modules.get("mcculw.ul", None), "_cbw"
    ):
        return  # real driver-backed module already loaded; don't clobber it

    ul_stub = types.ModuleType("mcculw.ul")

    class _StubDaqDeviceInfo:
        def __init__(self, board_num: int = 0) -> None:
            self.board_num = board_num

    device_info_stub = types.ModuleType("mcculw.device_info")
    device_info_stub.DaqDeviceInfo = _StubDaqDeviceInfo

    mcculw.ul = ul_stub
    mcculw.device_info = device_info_stub
    sys.modules["mcculw.ul"] = ul_stub
    sys.modules["mcculw.device_info"] = device_info_stub


_install_mcculw_hardware_stub()


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
