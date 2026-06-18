"""Integration test: AcquisitionBaseWorker driven end-to-end with a fake ADC.

No real mcculw hardware is touched -- the FakeADC double (see conftest.py)
stands in for an ADCBase-derived instance. This is the template to copy when
adding coverage for SequenceAcquisitionWorker / FrequencyAcquisitionWorker
without real hardware.
"""

import queue

import pytest

from workers.base_worker import AcquisitionBaseWorker

pytestmark = pytest.mark.integration


class _NoOpInitWorker(AcquisitionBaseWorker):
    """Worker subclass that skips real ADC creation; the ADC is injected via __init__."""

    def init_adc(self) -> None:
        pass


@pytest.fixture
def worker(make_fake_adc, monkeypatch, tmp_path):
    # Redirect brut-data persistence away from software/src/temp during the test.
    monkeypatch.setattr("workers.base_worker._BRUT_DATA_DIR", str(tmp_path))
    fake_adc = make_fake_adc(raw_block=list(range(16)))
    return _NoOpInitWorker(adc=fake_adc)


def _configure(worker):
    worker.send_command(
        {
            "action": "configure",
            "sequence": ["1", "|", "0", "|", "100.0", "D", "100.0", "D"],
            "nbr_of_points": 2,
            "config": {},
            "experiment_type": "Fluo",
            "tab_name": "test_tab",
        }
    )
    worker._process_pending_commands()


def _drain(q):
    items = []
    while True:
        try:
            items.append(q.get_nowait())
        except queue.Empty:
            break
    return items


def test_full_command_flow_produces_expected_results(worker):
    _configure(worker)

    worker.send_command({"action": "start"})
    worker._process_pending_commands()
    assert worker.acquiring is True
    assert worker.time_values == [0, 1]

    worker._execute_acquisition_step()
    worker._execute_acquisition_step()
    worker._execute_acquisition_step()  # nbr_of_points reached -> _finish_acquisition()

    assert worker.acquiring is False
    messages = _drain(worker.result_queue)

    live_messages = [m for m in messages if m["type"] == "live"]
    progress_messages = [m for m in messages if m["type"] == "progress"]
    final_messages = [m for m in messages if m["type"] == "final"]

    assert [m["x"] for m in live_messages] == [0, 1]
    assert [m["y"] for m in live_messages] == pytest.approx([8000.0, 8000.0])
    assert [m["progress"] for m in progress_messages] == [0.0, 0.5]

    assert len(final_messages) == 1
    final = final_messages[0]
    assert final["final_results"] == pytest.approx([8000.0, 8000.0])
    assert final["time_values"] == [0, 1]

    assert worker.adc.stop_acquisition_called is True
    assert worker.adc.stop_reader_called is True


def test_stop_command_halts_acquisition_before_completion(worker):
    _configure(worker)
    worker.send_command({"action": "start"})
    worker._process_pending_commands()

    worker._execute_acquisition_step()
    assert worker.current_point == 1

    worker.send_command({"action": "stop"})
    worker._process_pending_commands()

    assert worker.acquiring is False
    assert worker.adc.stop_acquisition_called is True
